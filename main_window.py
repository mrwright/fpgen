from __future__ import print_function

import pygtk
pygtk.require('2.0')
import gtk
import json

from defaults import (
    DEFAULT_DEFAULT_CLEARANCE_MILS,
    DEFAULT_DEFAULT_MASK_MILS,
)
from fparea import FPArea
from object_manager import ObjectManager
from primitives import (
    Ball,
    BallArray,
    CenterPoint,
    Coincident,
    DrawnLine,
    HorizDistance,
    Horizontal,
    HorizontalDrawnLine,
    MarkedLine,
    MeasuredHorizDistance,
    MeasuredVertDistance,
    Pad,
    PadArray,
    Pin,
    PinArray,
    SameDistance,
    VertDistance,
    Vertical,
    VerticalDrawnLine,
)
from ui_utils import (
    configuration_widget,
    StringEntry,
    UnitNumberEntry,
)
from units import UnitNumber

class MainWindow(gtk.Window):
    def _init_fields(self, filename):
        self._default_units = "mm"
        self._filename = filename
        self._modified = False

    def __init__(self, filename=None):
        super(MainWindow, self).__init__()
        self._init_fields(filename)

        self.set_geometry_hints(min_width=300, min_height=300)
        self.set_default_size(800, 600)
        self.connect("delete-event", gtk.main_quit)

        if filename:
            object_manager = self.load_file(filename)
        else:
            object_manager = self.new_blank_object_manager()

        fparea = FPArea(object_manager)
        fparea.connect("modified", self.set_modified)
        fparea.show()
        self.fparea = fparea
        fparea.set_flags(gtk.CAN_FOCUS)
        vbox = gtk.VBox(False)
        menu = self.create_menus()
        vbox.pack_start(menu, False, True, 0)
        hbox = gtk.HBox(False)
        vbox.add(hbox)
        buttonbar = self.create_button_bar()
        hbox.pack_start(buttonbar, False, True, 0)
        area_vbox = gtk.VBox()
        area_vbox.add(fparea)
        status_hbox = gtk.HBox()
        dof_label = gtk.Label("Degrees of freedom: ")
        dof_contents_label = gtk.Label("0")
        status_hbox.pack_start(dof_label, False, False, 0)
        status_hbox.pack_start(dof_contents_label, False, False, 0)
        fparea.connect("update-dof", self.update_dof, dof_contents_label)

        coord_label = gtk.Label("")
        status_hbox.pack_end(coord_label)
        fparea.connect("cursor-motion", self.fparea_cursor_motion, coord_label)

        area_vbox.pack_end(status_hbox, False, False, 0)
        dof_label.show()
        dof_contents_label.show()
        coord_label.show()
        status_hbox.show()
        area_vbox.show()
        hbox.add(area_vbox)
        hbox.show()
        vbox.show()
        self.add(vbox)

        self.update_title()

    def update_title(self):
        if self._modified:
            mod_char = '*'
        else:
            mod_char = ''
        if self._filename:
            display_fname = self._filename
        else:
            display_fname = "(Untitled)"
        self.set_title("FPGen - {} {}".format(display_fname, mod_char))

    def update_dof(self, _, dof, dof_label):
        dof_label.set_text(str(dof))

    def fparea_cursor_motion(self, _, x, y, coord_label):
        x = UnitNumber(x, "iu").to(self._default_units)
        y = UnitNumber(y, "iu").to(self._default_units)
        coord_label.set_text("({:.3f}, {:.3f})".format(x, y))

    def new_blank_object_manager(self):
        object_manager = ObjectManager(
            fp_name = "",
            default_clearance = UnitNumber(DEFAULT_DEFAULT_CLEARANCE_MILS,
                                           'mil'),
            default_mask = UnitNumber(DEFAULT_DEFAULT_MASK_MILS, 'mil')
        )
        CenterPoint.new(object_manager)
        return object_manager

    def load_file(self, filename):
        with open(filename) as f:
            contents = f.read()
        d = json.loads(contents)
        new_object_manager = ObjectManager.from_dict(d)
        self.fparea.set_object_manager(new_object_manager)

    def save_file(self, filename):
        d = self.fparea.object_manager.to_dict()
        with open(filename, "w") as f:
            f.write(json.dumps(d))

    def load_save_dialog(self, action):
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

    def set_modified(self, _, modified):
        self._modified = modified
        self.update_title()

    def do_load(self, _):
        chooser = self.load_save_dialog(gtk.FILE_CHOOSER_ACTION_OPEN)
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            fname = chooser.get_filename()
            self.load_file(fname)
            self._filename = fname
            self.fparea.clear_undo_buffer()
            self.update_title()

        chooser.destroy()

    def do_saveas(self, _):
        chooser = self.load_save_dialog(gtk.FILE_CHOOSER_ACTION_SAVE)
        chooser.set_do_overwrite_confirmation(True)
        response = chooser.run()
        if response == gtk.RESPONSE_OK:
            fname = chooser.get_filename()
            self.save_file(fname)
            self._filename = fname
            self.fparea.set_unmodified()
            self.update_title()

        chooser.destroy()

    def do_save(self, _):
        if self._filename:
            self.save_file(self._filename)
            self.fparea.set_unmodified()
            self.update_title()
        else:
            return self.do_saveas(_)

    def do_fp_settings(self, _):
        fparea = self.fparea
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

    def update_undo_redo(self, _, __, undo_item, redo_item):
        undo_item.set_sensitive(self.fparea.can_undo())
        redo_item.set_sensitive(self.fparea.can_redo())

    def do_undo_redo(self, undo):
        if undo:
            self.fparea.undo()
        else:
            self.fparea.redo()
        self.queue_draw()

    def create_menus(self):
        accel_group = gtk.AccelGroup()
        self.add_accel_group(accel_group)

        file_menu = gtk.Menu()
        open_item = gtk.ImageMenuItem(gtk.STOCK_OPEN, accel_group)
        save_item = gtk.ImageMenuItem(gtk.STOCK_SAVE, accel_group)
        saveas_item = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS, accel_group)
        quit_sep = gtk.SeparatorMenuItem()
        quit_item = gtk.ImageMenuItem(gtk.STOCK_QUIT, accel_group)
        open_item.connect("activate", self.do_load)
        save_item.connect("activate", self.do_save)
        saveas_item.connect("activate", self.do_saveas)
        quit_item.connect("activate", gtk.main_quit)
        file_menu.append(open_item)
        file_menu.append(save_item)
        file_menu.append(saveas_item)
        file_menu.append(quit_sep)
        file_menu.append(quit_item)
        open_item.show()
        save_item.show()
        saveas_item.show()
        quit_sep.show()
        quit_item.show()

        edit_menu = gtk.Menu()
        undo_item = gtk.ImageMenuItem(gtk.STOCK_UNDO, accel_group)
        undo_item.add_accelerator("activate", accel_group,
                                  ord('z'), gtk.gdk.CONTROL_MASK,
                                  gtk.ACCEL_VISIBLE)
        redo_item = gtk.ImageMenuItem(gtk.STOCK_REDO, accel_group)
        redo_item.add_accelerator("activate", accel_group,
                                  ord('y'), gtk.gdk.CONTROL_MASK,
                                  gtk.ACCEL_VISIBLE)
        edit_menu.connect("focus", self.update_undo_redo,
                          undo_item, redo_item)
        # TODO: update_undo_redo needs to be called in many more circumstances.
        edit_sep = gtk.SeparatorMenuItem()
        fp_settings_item = gtk.ImageMenuItem(gtk.STOCK_EDIT, accel_group)
        fp_settings_item.set_label("Footprint settings")
        fp_settings_item.connect("activate", self.do_fp_settings)
        edit_menu.append(undo_item)
        edit_menu.append(redo_item)
        edit_menu.append(edit_sep)
        edit_menu.append(fp_settings_item)
        #undo_item.set_sensitive(False)
        #redo_item.set_sensitive(False)
        undo_item.show()
        redo_item.show()
        undo_item.connect("activate", lambda _, s: s.do_undo_redo(True), self)
        redo_item.connect("activate", lambda _, s: s.do_undo_redo(False), self)
        edit_sep.show()
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
        ("Pin", Pin),
        ("PadAr", PadArray),
        ("PinAr", PinArray),
        ("BallAr", BallArray),
        ("MarkLine", MarkedLine),
        ("DrawLine", DrawnLine),
        ("HDrawLine", HorizontalDrawnLine),
        ("VDrawLine", VerticalDrawnLine),
        ("HCons", MeasuredHorizDistance),
        ("VCons", MeasuredVertDistance),
        ("==", SameDistance),
    ]

    def create_button_bar(self):
        fparea = self.fparea
        vbox = gtk.VBox(False)
        table = gtk.Table(8, 1, True)
        vbox.pack_start(table, False, False, 0)
        for idx, (btext, bcons) in enumerate(self.buttons):
            button = gtk.Button(btext)
            button.connect("pressed", lambda e,
                           bcons=bcons: fparea.add_new(bcons))
            button.unset_flags(gtk.CAN_FOCUS)
            button.show()
            table.attach(button, 0, 1, idx, idx + 1)
            fparea.buttons[button] = bcons
        fparea.update_buttons()
        table.show()
        vbox.show()
        return vbox


if __name__ == "__main__":
    main_window = MainWindow()
    main_window.present()
    print(main_window.focus_widget)
    gtk.main()
