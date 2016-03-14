from __future__ import print_function

import pygtk
pygtk.require('2.0')
import gobject
import gtk
import itertools

from geda_out import GedaOut
from math_utils import point_dist
from object_manager import ObjectManager
from primitives import (
    HorizDistance,
    Horizontal,
    Pad,
    Vertical,
)
from ui_utils import do_configuration

class FPArea(gtk.DrawingArea):
    __gsignals__ = {
        # Emitted when there's a (possible) change to the number
        # of degrees of freedom of our object manager.
        'update-dof': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (int,)),

        # When the cursor moves. Arguments are the internal coordinates,
        # not screen coordinates.
        'cursor-motion': (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          (float, float)),
    }

    def __init__(self, object_manager):
        super(FPArea, self).__init__()
        self.set_events(gtk.gdk.EXPOSURE_MASK
                        | gtk.gdk.LEAVE_NOTIFY_MASK
                        | gtk.gdk.BUTTON_PRESS_MASK
                        | gtk.gdk.BUTTON_RELEASE_MASK
                        | gtk.gdk.KEY_PRESS_MASK
                        | gtk.gdk.POINTER_MOTION_MASK
                        | gtk.gdk.POINTER_MOTION_HINT_MASK)
        self.connect("button-press-event", self.click_event)
        self.connect("button-release-event", self.release_event)
        self.connect("expose-event", self.expose_event)
        self.connect("motion-notify-event", self.motion_notify_event)
        self.connect("configure-event", self.configure_event)
        self.connect("key-press-event", self.key_press_event)
        self.connect("scroll-event", self.scroll_event)

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
        self.object_manager = object_manager
        self.active_object = None
        self.dragging_object = None
        self.selected_primitives = set()
        self.buttons = {}

        # Create the center point
        self.deselect_all()

        # _undo_list contains the entire undo history, *including the current
        # configuration*! _redo_list contains the redo history, excluding
        # the current configuration.
        self._undo_list = []
        self._redo_list = []

        self.snapshot()

    def scroll_event(self, _, event):
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

    def key_press_event(self, _, event):
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
        elif keyname == 'Delete':
            print(self.active_object)
            if self.active_object is not None:
                self.object_manager.delete_primitive(self.active_object)
            self.active_object = None
            self.recalculate()
            self.snapshot()
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
                res = do_configuration(self.active_object)
                self.recalculate()
                if res:
                    self.snapshot()
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

    def set_object_manager(self, object_manager):
        self.object_manager = object_manager
        self.selected_primitives.clear()
        self.update_buttons()
        self.recalculate()
        self.update_closest()
        self.queue_draw()

    def add_new(self, primitive_type):
        if primitive_type.can_create(self.selected_primitives):
            configuration = primitive_type.configure(self.selected_primitives)
            if configuration is not False:
                # TODO: x and y coords
                primitive_type.new(self.object_manager, 0, 0, configuration)
                self.deselect_all()
                self.snapshot()
        else:
            print("Cannot create constraint.")
        self.recalculate()
        self.update_closest()
        self.queue_draw()

    def configure_event(self, _, event):
        x, y, width, height = self.get_allocation()
        self.pixmap = gtk.gdk.Pixmap(self.window, width, height)
        self.pixmap.draw_rectangle(self.get_style().white_gc,
                                   True, 0, 0, width, height)

        return True

    def expose_event(self, _, event):
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
        if self.active_x is not None:
            dist = point_dist(
                (self.x, self.y),
                (self.active_x, self.active_y))
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

        active_primitive = ([self.active_object]
                            if self.active_object is not None else [])
        selected_primitives = [
            primitive for primitive in self.object_manager.draw_primitives
            if primitive is not self.active_object
            and primitive in self.selected_primitives]
        other_primitives = [
            primitive for primitive in self.object_manager.draw_primitives
            if primitive is not self.active_object
            and primitive not in self.selected_primitives]

        primitives = sorted(other_primitives +
                            selected_primitives +
                            active_primitive,
                            key = lambda x: x.ZORDER, reverse=True)

        for primitive in primitives:

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
        self.emit("update-dof", self.object_manager.degrees_of_freedom)

    def draw_pixmap(self, width, height):
        rect = (int(self.x-5), int(self.y-5), 10, 10)
        cr = self.pixmap.cairo_create()
        cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.rectangle(rect[0], rect[1], 10, 10)
        cr.fill()
        self.queue_draw()

    def motion_notify_event(self, _, event):
        if event.is_hint:
            x, y, state = event.window.get_pointer()
        else:
            x = event.x
            y = event.y

        orig_x, orig_y = self.x, self.y
        self.x, self.y = self.coord_map(x, y)
        self.emit("cursor-motion", self.x, self.y)
        if self.dragging:
            self.scale_x += (self.x - orig_x)
            self.scale_y += (self.y - orig_y)
            self.x, self.y = self.coord_map(x, y)
        if self.dragging_object is not None:
            self.dragging_object.drag(self.x - orig_x, self.y - orig_y)
        if self.active_x is not None and (
                self.dragging or self.dragging_object is not None):
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

    def snapshot(self):
        fp_dict = self.object_manager.to_dict()
        self._undo_list.append(fp_dict)
        del self._redo_list[:]

    def can_undo(self):
        return len(self._undo_list) > 1

    def can_redo(self):
        return len(self._redo_list) > 0

    def undo(self):
        self._redo_list.append(self._undo_list.pop())
        last_fp = self._undo_list[-1]
        new_object_manager = ObjectManager.from_dict(last_fp)
        self.set_object_manager(new_object_manager)

    def redo(self):
        next_fp = self._redo_list.pop()
        self._undo_list.append(next_fp)
        new_object_manager = ObjectManager.from_dict(next_fp)
        self.set_object_manager(new_object_manager)

    def click_event(self, _, event):
        x, y = self.coord_map(event.x, event.y)

        print(event.button)

        print("Click %s %s" % (x, y))
        if event.button == 1:
            if self.active_object is not None:
                print("Start drag")
                self.dragging_object = self.active_object
                drag_result = self.dragging_object.drag(0, 0)
                self.active_x = self.x
                self.active_y = self.y
                if drag_result:
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

    def release_event(self, _, event):
        print(event)
        if event.button == 1:
            print("Relase drag")
            if self.dragging_object is not None:
                self.snapshot()
            self.dragging_object = None
        elif event.button == 2:
            self.dragging = False

    def update_buttons(self):
        for button, buttoncls in self.buttons.iteritems():
            if buttoncls.can_create(self.selected_primitives):
                button.set_sensitive(True)
            else:
                button.set_sensitive(False)
