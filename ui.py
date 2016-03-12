from __future__ import print_function

import pygtk
pygtk.require('2.0')
import gtk
import itertools
import json

from defaults import (
    DEFAULT_DEFAULT_CLEARANCE_MILS,
    DEFAULT_DEFAULT_MASK_MILS,
)
from object_manager import ObjectManager
from primitives import (
    Ball,
    BallArray,
    CenterPoint,
    Coincident,
    HorizDistance,
    Horizontal,
    MarkedLine,
    Pad,
    PadArray,
    VertDistance,
    Vertical,
)
from geda_out import GedaOut
from ui_utils import (
    configuration_widget,
    NumberEntry,
    StringEntry,
    UnitNumberEntry,
    BoolEntry,
)
from units import UnitNumber

def do_configuration(primitive):
    print("Reconfigure %r" % primitive)
    dialog = gtk.Dialog("Configure")
    ((widget, widgets), validator) = primitive.reconfiguration_widget()
    if not validator:
        validator = lambda: all(widget.valid() for widget in widgets)
    dialog.get_content_area().add(widget)
    dialog.add_button("Ok", 1)
    dialog.add_button("Cancel", 2)
    parent = primitive.parent()
    if parent is not None:
        dialog.add_button("Edit parent", 3)
    while True:
        result = dialog.run()
        if result == 1:
            if not validator():
                continue
            primitive.reconfigure(widget, widgets)
        dialog.destroy()
        if result == 3:
            do_configuration(parent)
        break

class FPArea(gtk.DrawingArea):
    # TODO: this class should really be a standalone file area viewer with a better
    # interface. The UI stuff should be refactored.


    @classmethod
    def new(cls):
        self = cls()
        self.show()
        self.set_events(gtk.gdk.EXPOSURE_MASK
                        | gtk.gdk.LEAVE_NOTIFY_MASK
                        | gtk.gdk.BUTTON_PRESS_MASK
                        | gtk.gdk.BUTTON_RELEASE_MASK
                        | gtk.gdk.KEY_PRESS_MASK
                        | gtk.gdk.POINTER_MOTION_MASK
                        | gtk.gdk.POINTER_MOTION_HINT_MASK)
        self.connect("button-press-event", cls.click_event)
        self.connect("button-release-event", cls.release_event)
        self.connect("expose-event", cls.expose_event)
        self.connect("motion-notify-event", cls.motion_notify_event)
        self.connect("configure-event", cls.configure_event)
        self.connect("key-press-event", cls.key_press_event)
        self.connect("scroll-event", cls.scroll_event)

        # Where we last saw the mouse.
        self.x = 0
        self.y = 0
        # Where a "select other" in progress was started.
        self.active_x = None
        self.active_y = None
        # Offsets for converting between screen coordinates and logical
        # coordinates.
        self.scale_x = 100
        self.scale_y = 100
        # How far zoomed we are. Higher numbers mean more zoomed in.
        self.scale_factor = 1
        self.pixmap = None
        # Whether we're currently in the middle of a drag.
        self.dragging = False
        self.object_manager = ObjectManager(
            fp_name = "",
            default_clearance = UnitNumber(DEFAULT_DEFAULT_CLEARANCE_MILS,
                                           'mil'),
            default_mask = UnitNumber(DEFAULT_DEFAULT_MASK_MILS, 'mil')
        )
        self.active_object = None
        self.dragging_object = None
        self.selected_primitives = set()
        self.buttons = {}

        # Create the center point
        p = CenterPoint.new(self.object_manager)
        self.object_manager.add_primitive(p)
        self.deselect_all()

        self.update_dof_fn = None

        return self

    def scroll_event(self, event):
        # When the scroll wheel is used, zoom in or out.
        x, y = self.coord_map(event.x, event.y)
        print(x, y)
        if event.direction == gtk.gdk.SCROLL_UP:
            self.scale_factor *= 1.3
        elif event.direction == gtk.gdk.SCROLL_DOWN:
            self.scale_factor /= 1.3
        self.scale_x = event.x / self.scale_factor - x
        self.scale_y = event.y / self.scale_factor - y

        print(self.scale_factor, self.scale_x, self.scale_y)
        self.queue_draw()

    def recalculate(self):
        self.object_manager.update_points()
        self.update_closest()
        self.queue_draw()

    def deselect_all(self):
        self.selected_primitives.clear()
        self.update_buttons()

    def key_press_event(self, event):
        # TODO: refactor this so it's not some monolithic function
        # with what's effectively a huge case statement. It's not too
        # terrible right now, but as more gets added it will quickly
        # become worse.
        primitive_table = {
            'h': Horizontal,
            'v': Vertical,
            'd': HorizDistance,
        }
        keyname = gtk.gdk.keyval_name(event.keyval)
        print(keyname)
        if keyname == 'a':
            config = Pad.configure([])
            if config is not False:
                p = Pad.new(self.object_manager, self.x, self.y, config)
                #p = Ball(self.object_manager, self.x, self.y, 100)
                self.object_manager.add_primitive(p)
                self.recalculate()
        elif keyname == 'p':
            config = Array.configure([])
            if config is not False:
                p = Array.new(self.object_manager, self.x, self.y, config)
                self.object_manager.add_primitive(p)
                self.recalculate()
        elif keyname == 'Delete':
            print(self.active_object)
            if self.active_object is not None:
                self.object_manager.delete_primitive(self.active_object)
            self.active_object = None
            self.recalculate()
        elif keyname == 'dd':
            if len(self.selected_primitives) == 2:
                l = list(self.selected_primitives)
                p = HorizDistance(self.object_manager, l[0], l[1], 100, 30)
                self.object_manager.add_primitive(p)
                self.selected_primitives.clear()
            else:
                print("Select two points.")
            self.recalculate()
        elif keyname == 'space':
            if self.active_object is not None:
                if self.active_object in self.selected_primitives:
                    self.selected_primitives.remove(self.active_object)
                else:
                    self.selected_primitives.add(self.active_object)
                self.update_buttons()
        elif keyname == 'q':
            exit()
        elif keyname == 'w':
            GedaOut.write(self.object_manager)
        elif keyname == 'r':
            if self.active_object:
                do_configuration(self.active_object)
                self.recalculate()
        else:
            cls = primitive_table.get(keyname)
            if cls:
                if cls.can_create(self.selected_primitives):
                    configuration = cls.configure(self.selected_primitives)
                    if configuration:
                        p = cls.new(self.object_manager,
                                    0, 0,
                                    configuration)
                        self.object_manager.add_primitive(p)
                        self.deselect_all()
                else:
                    print("Cannot create constraint.")
            self.recalculate()
        self.update_closest()
        self.queue_draw()

    def save(self, fname):
        d = self.object_manager.to_dict()
        with open(fname, "w") as f:
            f.write(json.dumps(d))

    def load(self, fname):
        with open(fname) as f:
            contents = f.read()
        d = json.loads(contents)
        new_object_manager = ObjectManager.from_dict(d)
        self.object_manager = new_object_manager
        self.selected_primitives.clear()
        self.update_buttons()
        self.update_closest()
        self.queue_draw()

    def add_new(self, primitive_type):
        if primitive_type.can_create(self.selected_primitives):
            configuration = primitive_type.configure(self.selected_primitives)
            if configuration is not False:
                # TODO: x and y coords
                p = primitive_type.new(self.object_manager, 0, 0, configuration)
                # TODO: this should really be added as part of the constructor, or
                # all adding should happen here.
                self.object_manager.add_primitive(p)
                self.deselect_all()
        else:
            print("Cannot create constraint.")
        self.recalculate()
        self.update_closest()
        self.queue_draw()

    def configure_event(self, event):
        x, y, width, height = self.get_allocation()
        self.pixmap = gtk.gdk.Pixmap(self.window, width, height)
        self.pixmap.draw_rectangle(self.get_style().white_gc,
                                   True, 0, 0, width, height)

        return True

    def expose_event(self, event):
        x, y, width, height = event.area
        self.window.draw_drawable(self.get_style().fg_gc[gtk.STATE_NORMAL],
                                  self.pixmap, x, y, x, y, width, height)

        cr = self.window.cairo_create()
        # cr.rectangle(event.area.x, event.area.y,
        #              event.area.width, event.area.height)
        # cr.clip()
        self.draw(cr)
        return False

    def coord_map(self, x, y):
        '''
        Given pixel coordinates on the screen, return the corresponding
        logical coordinates.
        '''
        return (x / self.scale_factor - self.scale_x,
                y / self.scale_factor - self.scale_y)

    def update_closest(self):
        # TODO: point_dist should be its own utility function.
        if self.active_x is not None:
            dist =  self.object_manager.point_dist(
                (self.x, self.y),
                (self.active_x, self.active_y))
            print(dist, self.x, self.active_x)
            if dist < 100:
                return
        self.active_x = None
        self.active_y = None

        (p, dist) = self.object_manager.closest(self.x, self.y)

        if dist < 100:
            self.active_object = p
        else:
            self.active_object = None

    def draw(self, cr):
        cr.save()
        cr.scale(self.scale_factor, self.scale_factor)
        cr.translate(self.scale_x, self.scale_y)
        # cr.set_source_rgb(1, 1, 0)
        # cr.arc(self.x, self.y, 2, 0, 6.2)
        # cr.fill()

        # TODO: v
        self.object_manager.draw_primitives.sort(
            key=lambda x: x.ZORDER, reverse=True)

        for primitive in itertools.chain(
                (primitive for primitive in self.object_manager.draw_primitives
                 if primitive is not self.active_object
                 and primitive not in self.selected_primitives),
                (primitive for primitive in self.object_manager.draw_primitives
                 if primitive is not self.active_object
                 and primitive in self.selected_primitives),
                (self.active_object,) if self.active_object is not None else ()):
            cr.save()
            primitive.draw(cr,
                           primitive is self.active_object,
                           primitive in self.selected_primitives)
            cr.restore()
        if self.object_manager.point_coords:
            self.update_closest()
        self.update_dof()
        return

        # cr.restore()
        # cr.move_to(10, 10)
        # cr.show_text("(%s, %s)" % (x, y))
        # cr.stroke()

    def update_dof(self):
        if not self.update_dof_fn:
            return
        self.update_dof_fn(str(self.object_manager.degrees_of_freedom))

    def draw_pixmap(self, width, height):
        rect = (int(self.x-5), int(self.y-5), 10, 10)
        cr = self.pixmap.cairo_create()
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.rectangle(rect[0], rect[1], 10, 10)
        cr.fill()
        self.queue_draw()

    def motion_notify_event(self, event):
        if event.is_hint:
            x, y, state = event.window.get_pointer()
        else:
            x = event.x
            y = event.y

        orig_x, orig_y = self.x, self.y
        self.x, self.y = self.coord_map(x, y)
        if self.dragging:
            self.scale_x += (self.x - orig_x)
            self.scale_y += (self.y - orig_y)
            self.x, self.y = self.coord_map(x, y)
        if self.dragging_object is not None:
            self.dragging_object.drag(self.x - orig_x, self.y - orig_y)
        if self.active_x is not None and (self.dragging or self.dragging_object is not None):
            self.active_x += (self.x - orig_x)
            self.active_y += (self.y - orig_y)
        self.queue_draw()
        return True

    def select_other(self, menuitem, state, primitive):
        if state == gtk.STATE_NORMAL:
            print(primitive)
            self.active_object = primitive
            x, y = self.get_pointer()
            self.x, self.y = self.coord_map(x, y)
            self.active_x = self.x
            self.active_y = self.y
            self.queue_draw()

    def click_event(self, event):
        x, y = self.coord_map(event.x, event.y)

        print(event.button)

        print("Click %s %s" % (x, y))
        if event.button == 1:
            if self.active_object is not None:
                print("Start drag")
                self.dragging_object = self.active_object
                self.dragging_object.drag(0, 0)
                self.active_x = self.x
                self.active_y = self.y
                self.recalculate()
            else:
                self.dragging_object = None
            self.queue_draw()
        elif event.button == 2:
            self.dragging = True
        elif event.button == 3:
            menu = gtk.Menu()
            for _, primitive in self.object_manager.all_within(x, y, 1000):
                item = gtk.MenuItem(primitive.NAME)
                item.connect("state-changed", self.select_other, primitive)
                menu.append(item)
                item.show()
            menu.connect("deactivate", lambda *a, **kw: menu.destroy())
            menu.popup(None, None, None, event.button, event.time)
        return True

    def release_event(self, event):
        print(event)
        if event.button == 1:
            print("Relase drag")
            self.dragging_object = None
        elif event.button == 2:
            self.dragging = False

    def update_buttons(self):
        for button, buttoncls in self.buttons.iteritems():
            if buttoncls.can_create(self.selected_primitives):
                button.set_sensitive(True)
            else:
                button.set_sensitive(False)

def load_save_dialog(action):
    chooser = gtk.FileChooserDialog(
        action=action,
        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                 gtk.STOCK_OPEN, gtk.RESPONSE_OK))
    chooser.set_default_response(gtk.RESPONSE_OK)

    fpfiles = gtk.FileFilter()
    fpfiles.set_name("FPGen files")
    fpfiles.add_pattern("*.fpg")
    chooser.add_filter(fpfiles)

    allfiles = gtk.FileFilter()
    allfiles.set_name("All files")
    allfiles.add_pattern("*")
    chooser.add_filter(allfiles)

    return chooser

def do_load(_, fparea):
    chooser = load_save_dialog(gtk.FILE_CHOOSER_ACTION_OPEN)
    response = chooser.run()
    if response == gtk.RESPONSE_OK:
        fname = chooser.get_filename()
        fparea.load(fname)

    chooser.destroy()

def do_saveas(_, fparea):
    chooser = load_save_dialog(gtk.FILE_CHOOSER_ACTION_SAVE)
    chooser.set_do_overwrite_confirmation(True)
    response = chooser.run()
    if response == gtk.RESPONSE_OK:
        fname = chooser.get_filename()
        fparea.save(fname)

    chooser.destroy()

def do_fp_settings(_, fparea):
    dialog = gtk.Dialog("Footprint settings")
    widget, entry_widgets = configuration_widget(
        [
            ("Name",
             StringEntry(),
             fparea.object_manager.fp_name),
            ("Clearance",
             UnitNumberEntry(),
             fparea.object_manager.default_clearance),
            ("Mask",
             UnitNumberEntry(allow_empty=True),
             fparea.object_manager.default_mask),
        ]
    )
    dialog.get_content_area().add(widget)
    dialog.add_button("Ok", 1)
    dialog.add_button("Cancel", 2)
    while True:
        result = dialog.run()
        if result == 1:
            if not all(widget.valid() for widget in entry_widgets):
                continue
            fp_name = entry_widgets[0].val()
            clearance = entry_widgets[1].val()
            mask = entry_widgets[2].val()
            fparea.object_manager.fp_name = fp_name
            fparea.object_manager.default_clearance = clearance
            fparea.object_manager.default_mask = mask
        break
    dialog.destroy()

def create_menus(fparea):
    accel_group = gtk.AccelGroup()

    file_menu = gtk.Menu()
    open_item = gtk.ImageMenuItem(gtk.STOCK_OPEN, accel_group)
    save_item = gtk.ImageMenuItem(gtk.STOCK_SAVE, accel_group)
    saveas_item = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS, accel_group)
    quit_item = gtk.ImageMenuItem(gtk.STOCK_QUIT, accel_group)
    open_item.connect("activate", do_load, fparea)
    saveas_item.connect("activate", do_saveas, fparea)
    quit_item.connect("activate", gtk.main_quit)
    file_menu.append(open_item)
    file_menu.append(save_item)
    file_menu.append(saveas_item)
    file_menu.append(quit_item)
    open_item.show()
    save_item.show()
    saveas_item.show()
    quit_item.show()

    edit_menu = gtk.Menu()
    fp_settings_item = gtk.MenuItem("Footprint settings")
    fp_settings_item.connect("activate", do_fp_settings, fparea)
    edit_menu.append(fp_settings_item)
    fp_settings_item.show()
    edit_menu.show()

    menu_bar = gtk.MenuBar()
    menu_bar.show()
    file_item = gtk.MenuItem("File")
    file_item.set_submenu(file_menu)
    file_item.show()
    edit_item = gtk.MenuItem("Edit")
    edit_item.set_submenu(edit_menu)
    edit_item.show()
    menu_bar.append(file_item)
    menu_bar.append(edit_item)

    return menu_bar

buttons = [
    ("Coinc", Coincident),
    ("Horiz", Horizontal),
    ("Vert", Vertical),
    ("HDist", HorizDistance),
    ("VDist", VertDistance),
    ("Ball", Ball),
    ("Pad", Pad),
    ("PadAr", PadArray),
    ("BallAr", BallArray),
    ("MarkLine", MarkedLine),
]

def create_button_bar(fparea):
    vbox = gtk.VBox(False)
    table = gtk.Table(8, 1, True)
    vbox.pack_start(table, False, False, 0)
    for idx, (btext, bcons) in enumerate(buttons):
        button = gtk.Button(btext)
        button.connect("pressed", lambda e, bcons=bcons: fparea.add_new(bcons))
        button.unset_flags(gtk.CAN_FOCUS)
        button.show()
        table.attach(button, 0, 1, idx, idx + 1)
        fparea.buttons[button] = bcons
    fparea.update_buttons()
    table.show()
    vbox.show()
    return vbox

def run():
    window = gtk.Window()
    window.set_geometry_hints(min_width=300, min_height=300)
    window.set_default_size(800, 600)
    window.connect("delete-event", gtk.main_quit)
    fparea = FPArea.new()
    fparea.set_flags(gtk.CAN_FOCUS)
    vbox = gtk.VBox(False)
    menu = create_menus(fparea)
    vbox.pack_start(menu, False, True, 0)
    hbox = gtk.HBox(False)
    vbox.add(hbox)
    buttonbar = create_button_bar(fparea)
    hbox.pack_start(buttonbar, False, True, 0)
    area_vbox = gtk.VBox()
    area_vbox.add(fparea)
    status_hbox = gtk.HBox()
    dof_label = gtk.Label("Degrees of freedom: ")
    dof_contents_label = gtk.Label("0")
    status_hbox.pack_start(dof_label, False, False, 0)
    status_hbox.pack_start(dof_contents_label, False, False, 0)
    fparea.update_dof_fn = dof_contents_label.set_text

    area_vbox.pack_end(status_hbox, False, False, 0)
    dof_label.show()
    dof_contents_label.show()
    status_hbox.show()
    area_vbox.show()
    hbox.add(area_vbox)
    hbox.show()
    vbox.show()
    window.add(vbox)
    window.present()
    window.connect('key-press-event', lambda e, f: print(e, f))
    print(window.focus_widget)
    gtk.main()

if __name__ == "__main__":
    run()
