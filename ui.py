from __future__ import print_function

import pygtk
pygtk.require('2.0')
import gtk
import json

from object_manager import ObjectManager
from primitives import (Pad, Coincident, MarkedLine, Horizontal, Vertical, CenterPoint,
                        PadArray, BallArray, HorizDistance, VertDistance, Ball)
from geda_out import GedaOut

def do_configuration(primitive):
    print("Reconfigure %r" % primitive)
    dialog = gtk.Dialog("Configure")
    (widget, widgets) = primitive.reconfiguration_widget()
    dialog.get_content_area().add(widget)
    dialog.add_button("Ok", 1)
    dialog.add_button("Cancel", 2)
    parent = primitive.parent()
    if parent is not None:
        dialog.add_button("Edit parent", 3)
    result = dialog.run()
    if result == 1:
        primitive.reconfigure(widget, widgets)
    dialog.destroy()
    if result == 3:
        do_configuration(parent)

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
        # Offsets for converting between screen coordinates and logical
        # coordinates.
        self.scale_x = 100
        self.scale_y = 100
        # How far zoomed we are. Higher numbers mean more zoomed in.
        self.scale_factor = 1
        self.pixmap = None
        # Whether we're currently in the middle of a drag.
        self.dragging = False
        self.object_manager = ObjectManager(6, 2)
        self.active_object = None
        self.dragging_object = None
        self.selected_primitives = set()
        self.buttons = {}

        # Create the center point
        p = CenterPoint.new(self.object_manager)
        self.object_manager.add_primitive(p)
        self.deselect_all()

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
        for primitive in self.selected_primitives:
            primitive.deselect()
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
                    self.active_object.deselect()
                else:
                    self.selected_primitives.add(self.active_object)
                    self.active_object.select()
                self.update_buttons()
        elif keyname == 'q':
            exit()
        elif keyname == 'w':
            GedaOut.write(self.object_manager.primitives)
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
        (p, dist) = self.object_manager.closest(self.x, self.y)

        if dist < 100:
            if self.active_object is not None and p is not None:
                self.active_object.deactivate()
            self.active_object = p
            if p is not None:
                p.activate()
        else:
            if self.active_object is not None:
                self.active_object.deactivate()
            self.active_object = None

    def draw(self, cr):
        cr.save()
        cr.scale(self.scale_factor, self.scale_factor)
        cr.translate(self.scale_x, self.scale_y)
        # cr.set_source_rgb(1, 1, 0)
        # cr.arc(self.x, self.y, 2, 0, 6.2)
        # cr.fill()
        for primitive in self.object_manager.draw_primitives:
            cr.save()
            primitive.draw(cr)
            cr.restore()
        if self.object_manager.point_coords:
            self.update_closest()
        return

        # cr.restore()
        # cr.move_to(10, 10)
        # cr.show_text("(%s, %s)" % (x, y))
        # cr.stroke()

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
        self.queue_draw()
        return True

    def click_event(self, event):
        x, y = self.coord_map(event.x, event.y)

        print(event.button)

        print("Click %s %s" % (x, y))
        if event.button == 1:
            if self.active_object is not None:
                print("Start drag")
                self.dragging_object = self.active_object
                self.dragging_object.drag(0, 0)
                self.recalculate()
            else:
                self.dragging_object = None
            self.queue_draw()
        elif event.button == 2:
            self.dragging = True
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

def do_load(fparea):
    chooser = load_save_dialog(gtk.FILE_CHOOSER_ACTION_OPEN)
    response = chooser.run()
    if response == gtk.RESPONSE_OK:
        fname = chooser.get_filename()
        fparea.load(fname)

    chooser.destroy()

def do_saveas(fparea):
    chooser = load_save_dialog(gtk.FILE_CHOOSER_ACTION_SAVE)
    chooser.set_do_overwrite_confirmation(True)
    response = chooser.run()
    if response == gtk.RESPONSE_OK:
        fname = chooser.get_filename()
        fparea.save(fname)

    chooser.destroy()

def create_menus(fparea):
    accel_group = gtk.AccelGroup()
    file_menu = gtk.Menu()
    open_item = gtk.ImageMenuItem(gtk.STOCK_OPEN, accel_group)
    save_item = gtk.ImageMenuItem(gtk.STOCK_SAVE, accel_group)
    saveas_item = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS, accel_group)
    quit_item = gtk.ImageMenuItem(gtk.STOCK_QUIT, accel_group)
    open_item.connect("activate", lambda x: do_load(fparea))
    saveas_item.connect("activate", lambda x: do_saveas(fparea))
    quit_item.connect("activate", gtk.main_quit)
    file_menu.append(open_item)
    file_menu.append(save_item)
    file_menu.append(saveas_item)
    file_menu.append(quit_item)
    open_item.show()
    save_item.show()
    saveas_item.show()
    quit_item.show()

    menu_bar = gtk.MenuBar()
    menu_bar.show()
    file_item = gtk.MenuItem("File")
    file_item.show()
    file_item.set_submenu(file_menu)
    menu_bar.append(file_item)

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
    window.set_geometry_hints(min_width=600, min_height=600)
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
    hbox.add(fparea)
    hbox.show()
    vbox.show()
    window.add(vbox)
    window.present()
    window.connect('key-press-event', lambda e, f: print(e, f))
    print(window.focus_widget)
    gtk.main()

if __name__ == "__main__":
    run()
