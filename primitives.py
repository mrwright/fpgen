import pygtk
pygtk.require('2.0')
import gtk
import math

from numbering import ALL_NUMBERINGS, NUMBER_CONST_HEIGHT, NUMBER_CONST_WIDTH
from ui_utils import configuration_widget_items, configuration_widget, reconfigure

class Primitive(object):
    def __init__(self, object_manager, number=None, clearance=None, mask=None):
        # TODO: active and selected should be parameters to draw, not properties.
        self._active = False
        self._selected = False
        self._clearance = clearance
        self._mask = mask
        self._object_manager = object_manager
        self._number = number

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        '''
        Construct this primitive.
        '''
        pass

    def to_dict(self):
        return NotImplementedError()

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        raise NotImplementedError()

    def dependencies(self):
        '''
        All primitives we depend on. They might be able to exist independently
        of them, but we can't exist without them, and if one of them is
        deleted we should be as well. For example, a constraint between two
        points depends on both of those points.

        Child primitives should not explicitly list their parents as
        dependencies.
        '''
        return []

    def constraints(self):
        '''
        Return a list of constraints.
        Each constraint is a tuple
            ([(point1, x_weight1, y_weight1), ...], target)
        representing the constraint
            point1.x * x_weight1 + point1.y * y_weight1 + ... = target

        Note that the points here are actually indices of points in the
        ObjectManager, not Point objects. (So point1.x really means
        "the x coordinate of the point with index point1".)
        '''
        return []

    def children(self):
        '''
        All primitives that are considered "children" of this one; that is,
        are basically a part of this primitive and don't exist on their own.
        If we're deleted, all of our children will be deleted, too.

        For example, in a pad array, each individual pad is a child.
        '''
        return []

    def dist(self, p):
        '''
        The "distance" from us to the given point.
        What this means depends on the object itself. When the mouse moves,
        the object "closest" to the cursor will be highlighted, and so
        distances should be arranged in a way that this makes sense.
        "None" is used to represent "infinite distance."
        '''
        return None

    def draw(self, cr):
        '''
        Draw this object using the given Cairo context.
        '''
        pass

    def activate(self):
        '''
        Set ourselves as active. This can affect how we're drawn.
        '''
        self._active = True

    def deactivate(self):
        self._active = False

    def active(self):
        return self._active

    def select(self):
        '''
        Set ourselves as selected. This can affect how we're drawn.
        '''
        self._selected = True

    def deselect(self):
        self._selected = False

    def selected(self):
        return self._selected

    def delete(self):
        pass

    def drag(self, offs_x, offs_y):
        '''
        Drag ourselves by a certain delta in the x and y directions.
        This will likely want to drag all children.
        '''
        pass

    @classmethod
    def configure(cls, objects):
        return None

    @classmethod
    def placeable(cls):
        return False

    @classmethod
    def can_create(cls, objects):
        return False

    def parent(self):
        return self._object_manager.parent_map.get(self)

    def number(self):
        if self._number is not None:
            # We're assigned a number directly, so return it.
            return self._number
        # We don't have a number assigned directly, so fall back on asking if the
        # parent assigns a number to us.
        parent = self.parent()
        if parent is not None:
            return parent.number_of(self)

    def number_of(self, child):
        return None

    def clearance(self):
        if self._clearance is not None:
            return self._clearance
        else:
            parent = self.parent()
            if parent:
                return parent.clearance()
            else:
                return self._object_manager.default_clearance

    def mask(self):
        if self._mask is not None:
            return self._mask
        else:
            parent = self.parent()
            if parent:
                return parent.mask()
            else:
                return self._object_manager.default_mask

    def reconfiguration_widget(self):
        return None

    def reconfigure(self, widget, other_widgets):
        raise NotImplementedError()

    def can_delete(self):
        return True

    @classmethod
    def TYPE(cls):
        for type_id, ty in enumerate(PRIMITIVE_TYPES):
            if ty == cls:
                return type_id
        raise ValueError()

class Point(Primitive):
    '''
    This class wraps the ObjectManager's points.
    '''
    def __init__(self, object_manager, point):
        super(Point, self).__init__(object_manager)
        self.p = point

    @classmethod
    def new(cls, object_manager, x, y):
        point = object_manager.alloc_point(x, y)
        return cls(object_manager, point)

    @property
    def x(self):
        return self._object_manager.point_x(self.p)

    @property
    def y(self):
        return self._object_manager.point_y(self.p)

    def point(self):
        '''
        Return the index of this point in the ObjectManager.
        '''
        return self.p

    def dist(self, p):
        return self._object_manager.point_dist((self.x, self.y), p)

    def draw(self, cr):
        if self.active():
            cr.set_source_rgb(1, 0, 0)

            cr.arc(self.x, self.y, 2, 0, 6.2)
            cr.fill()

        if self.selected():
            cr.set_source_rgb(0, 0, 1)
        else:
            cr.set_source_rgb(0.5, 0.5, 0.5)
        cr.arc(self._object_manager.point_x(self.p),
               self._object_manager.point_y(self.p), 1, 0, 6.2)
        cr.fill()

    def drag(self, offs_x, offs_y):
        x, y = self._object_manager.point_coords(self.point())
        x += offs_x
        y += offs_y
        self._object_manager.set_point_coords(self.point(), x, y)

    def delete(self):
        self._object_manager.free_point(self.point())

    def to_dict(self):
        return dict(
            point_idx=self.p
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        return cls(object_manager,
                   dictionary['point_idx'])

class CenterPoint(Point):
    def __init__(self, object_manager, point):
        super(CenterPoint, self).__init__(object_manager, point)

    @classmethod
    def new(cls, object_manager):
        point = object_manager.alloc_point(0, 0)
        return cls(object_manager, point)

    @classmethod
    def can_create(cls, objects):
        return not objects

    def children(self):
        # This prevents this point from being deletable.
        return [self]

    def constraints(self):
        return [
            ([(self.p, 1, 0)], 0),
            ([(self.p, 0, 1)], 0)
        ]

    def drag(self, offs_x, offs_y):
        pass

    def can_delete(self):
        return False

class TileablePrimitive(Primitive):
    def dimensions_to_constrain(self):
        return []

    def center_point(self):
        return None

class Pad(TileablePrimitive):
    def __init__(self, object_manager, points, number=None, clearance=None, mask=None):
        super(Pad, self).__init__(object_manager, number, clearance, mask)
        self.points = points

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        w = configuration['w']
        h = configuration['h']
        # Pads consist of 9 points, evenly spaced in a 3x3 grid.
        points = []
        for j in range(3):
            for i in range(3):
                points.append(
                    Point.new(object_manager,
                              x + (i - 1) * w/2,
                              y + (j - 1) * h/2)
                )
        for point in points:
            object_manager.add_primitive(point, draw=False,
                                         check_overconstraints=False)
        return cls(object_manager, points)

    @classmethod
    def configure(cls, objects, w=100, h=100):
        # TODO: configuration dialog?
        return dict(w=w, h=h)

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Number", int, self._number),
                ("Clearance", int, self._clearance),
                ("Mask", int, self._mask),
            ]
        )

    def reconfigure(self, widget, other_widgets):
        (self._number,
         self._clearance,
         self._mask) = reconfigure(other_widgets)

    @classmethod
    def placeable(cls):
        return True

    @classmethod
    def can_create(cls, objects):
        return not objects

    def children(self):
        return self.points

    def p(self, x, y):
        return self.points[x + 3 * y].point()

    @property
    def x0(self):
        return min(self.points[0].x, self.points[8].x)

    @property
    def x1(self):
        return max(self.points[0].x, self.points[8].x)

    @property
    def y0(self):
        return min(self.points[0].y, self.points[8].y)

    @property
    def y1(self):
        return max(self.points[0].y, self.points[8].y)

    @property
    def w(self):
        return self.x1 - self.x0

    @property
    def h(self):
        return self.y1 - self.y0

    def dist(self, p):
        # We consider the distance to us to be 10 to anywhere inside us,
        # and infinite to anywhere else. This ensures we'll only be active
        # when the mouse is actually on the pad, but that individual points
        # in us can still be active, too.
        x, y = p[0], p[1]
        if x > self.x0 and x < self.x1 and y > self.y0 and y < self.y1:
            return 10
        else:
            return None

    def constraints(self):
        # Points in a row should be aligned horizontally; points in a column
        # vertically.
        horiz_constraints = [
            ([(self.p(i, j), 0, 1), (self.p(i+1, j), 0, -1)], 0)
            for i in range(2) for j in range(3)
        ]
        vert_constraints = [
            ([(self.p(j, i), 1, 0), (self.p(j, i+1), -1, 0)], 0)
            for i in range(2) for j in range(3)
        ]
        # Spacing should be equal, in the horizontal and vertical directions.
        # (Note that this only needs to be applied to the first row/column;
        # the horizontal/vertical constraints take care of the rest.)
        eq_horiz_constraints = [
            ([(self.p(0, 0), 1, 0),
              (self.p(1, 0), -2, 0),
              (self.p(2, 0), 1, 0)], 0)
        ]
        eq_vert_constraints = [
            ([(self.p(0, 0), 0, 1),
              (self.p(0, 1), 0, -2),
              (self.p(0, 2), 0, 1)], 0)
        ]
        return (horiz_constraints +
                vert_constraints +
                eq_horiz_constraints +
                eq_vert_constraints)

    def draw(self, cr):
        cr.save()
        if self.selected():
            cr.set_source_rgb(0, 0, 0.7)
        elif self.active():
            cr.set_source_rgb(0.7, 0, 0)
        else:
            cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.rectangle(self.x0, self.y0, self.w, self.h)
        cr.fill()
        cr.restore()
        cr.save()
        if self.number() is not None:
            cr.move_to(self.x0 + self.w/2, self.y0 + self.h/2)
            cr.show_text(self.number())
            cr.stroke()
        for child in self.children():
            child.draw(cr)
        cr.restore()

    def drag(self, offs_x, offs_y):
        for point in self.points:
            point.drag(offs_x, offs_y)

    def dimensions_to_constrain(self, multiplier=1):
        # When in an array, we want the height and width of all pads to be equal.
        return [[(self.p(0, 0), multiplier, 0),
                 (self.p(2, 0), -multiplier, 0)],
                [(self.p(0, 0), 0, multiplier),
                 (self.p(0, 2), 0, -multiplier)]]

    def center_point(self):
        return self.p(1, 1)

    def to_dict(self):
        point_indices = [
            self._object_manager.primitive_idx(point)
            for point in self.points]
        return dict(
            points=point_indices,
            deps=point_indices,
            number=self._number,
            clearance=self._clearance,
            mask=self._mask,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        return cls(object_manager,
                   [object_manager.primitives[idx] for idx in dictionary['points']],
                   dictionary['number'],
                   dictionary['clearance'],
                   dictionary['mask'])

class Ball(TileablePrimitive):
    def __init__(self, object_manager, points, number=None):
        super(Ball, self).__init__(object_manager, number)
        self.points = points

    @classmethod
    def new(cls, object_manager, x, y, configuration, r=20):
        # Five points: the center point, and four at the compass points around it.
        points = [
            Point.new(object_manager, x, y - r/2),
            Point.new(object_manager, x - r/2, y),
            Point.new(object_manager, x, y),
            Point.new(object_manager, x + r/2, y),
            Point.new(object_manager, x, y + r/2),
        ]
        for point in points:
            object_manager.add_primitive(point, draw=False,
                                         check_overconstraints=False)
        return cls(object_manager, points)

    @classmethod
    def configure(cls, objects):
        return None

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Number", int, self._number),
                ("Clearance", int, self._clearance),
                ("Mask", int, self._mask),
            ]
        )

    def reconfigure(self, widget, other_widgets):
        (self._number,
         self._clearance,
         self._mask) = reconfigure(other_widgets)

    @classmethod
    def placeable(cls):
        return True

    @classmethod
    def can_create(cls, objects):
        return not objects

    @property
    def x(self):
        return self.points[2].x

    @property
    def y(self):
        return self.points[2].y

    @property
    def r(self):
        return self.points[3].x - self.points[2].x

    def children(self):
        return self.points

    def p(self, x):
        return self.points[x].point()

    def dist(self, p):
        # We consider the distance to us to be 10 to anywhere inside us,
        # and infinite to anywhere else.
        x, y = p[0], p[1]
        cx, cy = self.x, self.y
        r = self.r
        if (x - cx) * (x - cx) + (y - cy) * (y - cy) < r * r:
            return 10
        else:
            return None

    def constraints(self):
        # Points in a row should be aligned horizontally; points in a column
        # vertically.
        horiz_constraints = [
            ([(self.p(1), 0, 1), (self.p(2), 0, -1)], 0),
            ([(self.p(1), 0, 1), (self.p(3), 0, -1)], 0)
        ]
        vert_constraints = [
            ([(self.p(0), 1, 0), (self.p(2), -1, 0)], 0),
            ([(self.p(0), 1, 0), (self.p(4), -1, 0)], 0)
        ]
        # Spacing should be equal, in the horizontal and vertical directions.
        eq_horiz_constraints = [
            ([(self.p(1), 1, 0),
              (self.p(2), -2, 0),
              (self.p(3), 1, 0)], 0)
        ]
        eq_vert_constraints = [
            ([(self.p(0), 0, 1),
              (self.p(2), 0, -2),
              (self.p(4), 0, 1)], 0)
        ]
        # Finally, the radius is the same in any direction.
        eq_constraints = [
            ([(self.p(2), -1, 1),
              (self.p(3), 1, 0),
              (self.p(4), 0, -1),
            ], 0)
        ]
        return (horiz_constraints +
                vert_constraints +
                eq_horiz_constraints +
                eq_vert_constraints +
                eq_constraints)

    def draw(self, cr):
        cr.save()
        if self.selected():
            cr.set_source_rgb(0, 0, 0.7)
        elif self.active():
            cr.set_source_rgb(0.7, 0, 0)
        else:
            cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.arc(self.x, self.y, self.r, 0, 2 * math.pi)
        cr.fill()
        cr.restore()
        if self.number() is not None:
            cr.move_to(self.x, self.y)
            cr.show_text(self.number())
            cr.stroke()
        cr.save()
        for child in self.children():
            child.draw(cr)
        cr.restore()

    def drag(self, offs_x, offs_y):
        for point in self.points:
            point.drag(offs_x, offs_y)

    def dimensions_to_constrain(self, multiplier=1):
        # When in an array, we want the height and width of all pads to be equal.
        return [[(self.p(3), multiplier, 0),
                 (self.p(2), -multiplier, 0)]]

    def center_point(self):
        return self.p(2)

    def to_dict(self):
        point_indices = [
            self._object_manager.primitive_idx(point)
            for point in self.points]
        return dict(
            points=point_indices,
            deps=point_indices,
            number=self._number,
            clearance=self._clearance,
            mask=self._mask,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        return cls(object_manager,
                   [object_manager.primitives[idx] for idx in dictionary['points']],
                   dictionary['number'],
                   dictionary['clearance'],
                   dictionary['mask'])

class TwoPointConstraint(Primitive):
    '''
    Base class for any constraint between two points.
    '''
    def __init__(self, object_manager, objects):
        assert self.can_create(objects)
        l = list(objects)
        p1, p2 = l[0], l[1]
        super(TwoPointConstraint, self).__init__(object_manager)
        self.p1 = p1
        self.p2 = p2

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        objects = configuration['objects']
        return cls(object_manager, objects)

    @classmethod
    def configure(cls, objects):
        return dict(
            objects=objects
        )

    @classmethod
    def can_create(cls, objects):
        return len(objects) == 2 and all(isinstance(o, Point) for o in objects)

    @classmethod
    def placeable(cls):
        return False

    def dependencies(self):
        return [self.p1, self.p2]

    def to_dict(self):
        point_indices = [
            self._object_manager.primitive_idx(point)
            for point in (self.p1, self.p2)]
        return dict(
            points=point_indices,
            deps=point_indices,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        return cls(object_manager,
                   [object_manager.primitives[idx] for idx in dictionary['points']])

class Horizontal(TwoPointConstraint):
    def __init__(self, object_manager, objects):
        super(Horizontal, self).__init__(object_manager, objects)

    def constraints(self):
        return [
            ([(self.p1.point(), 0, 1), (self.p2.point(), 0, -1)], 0)
        ]

    def dist(self, p):
        x, y = p[0], p[1]
        if self.p1.x < self.p2.x:
            p1, p2 = self.p1, self.p2
        else:
            p1, p2 = self.p2, self.p1
        if x < p1.x:
            return 10 + self._object_manager.point_dist(p, (p1.x, p1.y))
        elif x > p2.x:
            return 10 + self._object_manager.point_dist(p, (p2.x, p2.y))
        else:
            return 10 + (y - p1.y) * (y - p1.y)

    def draw(self, cr):
        if self.selected():
            cr.set_source_rgb(0.4, 0.4, 1)
            cr.set_line_width(0.5)
            cr.set_dash([2, 2], 2)
            cr.move_to(self.p1.x, self.p1.y)
            cr.line_to(self.p2.x, self.p2.y)
            cr.stroke()
        if self.active():
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 1, 0)
        cr.set_line_width(0.5)
        cr.set_dash([2, 2])
        cr.move_to(self.p1.x, self.p1.y)
        cr.line_to(self.p2.x, self.p2.y)
        cr.stroke()


class Vertical(TwoPointConstraint):
    def __init__(self, object_manager, objects):
        super(Vertical, self).__init__(object_manager, objects)

    def constraints(self):
        return [
            ([(self.p1.point(), 1, 0), (self.p2.point(), -1, 0)], 0)
        ]

    def dist(self, p):
        x, y = p[0], p[1]
        if self.p1.y < self.p2.y:
            p1, p2 = self.p1, self.p2
        else:
            p1, p2 = self.p2, self.p1
        if y < p1.y:
            return 10 + self._object_manager.point_dist(p, (p1.x, p1.y))
        elif y > p2.y:
            return 10 + self._object_manager.point_dist(p, (p2.x, p2.y))
        else:
            return 10 + (x - p1.x) * (x - p1.x)

    def draw(self, cr):
        if self.selected():
            cr.set_source_rgb(0, 0, 1)
        elif self.active():
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 1, 0)
        cr.set_line_width(0.5)
        cr.set_dash([5, 5])
        cr.move_to(self.p1.x, self.p1.y)
        cr.line_to(self.p2.x, self.p2.y)
        cr.stroke()

class DistanceConstraint(TwoPointConstraint):
    def __init__(self, object_manager, p1, p2, dist, label_dist):
        super(DistanceConstraint, self).__init__(object_manager, [p1, p2])

        self.p1 = p1
        self.p2 = p2
        self.distance = dist

        self.label_distance = label_dist

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        p1 = configuration['p1']
        p2 = configuration['p2']
        dist = configuration['dist']
        if cls.horiz and (p1.x > p2.x) or not cls.horiz and (p1.y > p2.y):
            p1, p2 = p2, p1
        return cls(object_manager, p1, p2, dist, 100)

    @classmethod
    def configure(cls, objects):
        if cls.horiz:
            dialog = gtk.Dialog("Horizontal distance")
        else:
            dialog = gtk.Dialog("Vertical distance")
        array = gtk.Table(1, 2)
        label1 = gtk.Label("Distance: ")
        array.attach(label1, 0, 1, 0, 1)
        entry1 = gtk.Entry()
        array.attach(entry1, 1, 2, 0, 1)
        label1.show()
        entry1.show()
        array.show()
        dialog.get_content_area().add(array)
        # widget.connect("clicked", lambda x: win2.destroy())
        dialog.add_button("Ok", 1)
        dialog.add_button("Cancel", 2)
        result = dialog.run()
        if result == 1:
            result = float(entry1.get_text())
        else:
            result = False
        dialog.destroy()
        obj_list = list(objects)

        return dict(
            dist=result,
            p1=obj_list[0],
            p2=obj_list[1],
        )

    def constraints(self):
        if self.horiz:
            return [
                ([(self.p2.point(), 1, 0), (self.p1.point(), -1, 0)], self.distance)
            ]
        else:
            return [
                ([(self.p2.point(), 0, 1), (self.p1.point(), 0, -1)], self.distance)
            ]

    def draw(self, cr):
        if self.selected():
            cr.set_source_rgb(0, 0, 1)
        elif self.active():
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(0.3)
        cr.move_to(self.p1.x, self.p1.y)
        if self.horiz:
            cr.line_to(self.p1.x, self.p1.y + self.label_distance)
        else:
            cr.line_to(self.p1.x + self.label_distance, self.p1.y)
        cr.stroke()
        cr.move_to(self.p2.x, self.p2.y)
        if self.horiz:
            # Note: the p1 here is not a bug.
            cr.line_to(self.p2.x, self.p1.y + self.label_distance)
        else:
            cr.line_to(self.p1.x + self.label_distance, self.p2.y)
        cr.stroke()
        if self.horiz:
            cr.move_to(self.p1.x, self.p1.y + self.label_distance)
        else:
            cr.move_to(self.p1.x + self.label_distance, self.p2.y)
        cr.show_text("%s" % (self.distance,))
        cr.stroke()

    def dist(self, p):
        if self.horiz:
            return self._object_manager.point_dist(
                p,
                (self.p1.x,
                 self.p1.y + self.label_distance)
            )
        else:
            return self._object_manager.point_dist(
                p,
                (self.p1.x + self.label_distance,
                 self.p2.y)
            )

    def drag(self, offs_x, offs_y):
        if self.horiz:
            self.label_distance += offs_y
        else:
            self.label_distance += offs_x

    def to_dict(self):
        dictionary = super(DistanceConstraint, self).to_dict()
        dictionary.update(dict(
            distance=self.distance,
            label_distance=self.label_distance
        ))
        return dictionary

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        p1, p2 = tuple([object_manager.primitives[idx] for idx in dictionary['points']])
        return cls(object_manager,
                   p1, p2, dictionary['distance'], dictionary['label_distance']
        )

class HorizDistance(DistanceConstraint):
    horiz = True

class VertDistance(DistanceConstraint):
    horiz = False

class Coincident(TwoPointConstraint):
    def __init__(self, object_manager, objects):
        super(Coincident, self).__init__(object_manager, objects)

    def constraints(self):
        return [
            ([(self.p1.point(), 0, 1), (self.p2.point(), 0, -1)], 0),
            ([(self.p1.point(), 1, 0), (self.p2.point(), -1, 0)], 0),
        ]

    def dist(self, p):
        dist = self._object_manager.point_dist(
            p, (self.p1.x, self.p1.y))
        if dist < 10:
            return dist + 1
        else:
            return dist - 1

    def draw(self, cr):
        if self.active():
            cr.set_source_rgb(1, 0, 0)
        elif self.selected():
            # TODO: if both are the case.
            cr.set_source_rgb(0.4, 0.4, 1)
        else:
            cr.set_source_rgb(0, 1, 0)
        cr.set_line_width(0.5)
        #cr.set_dash([2, 2])
        cr.move_to(self.p1.x - 5, self.p1.y - 5)
        cr.line_to(self.p2.x + 5, self.p2.y + 5)
        cr.stroke()
        cr.move_to(self.p1.x + 5, self.p1.y - 5)
        cr.line_to(self.p2.x - 5, self.p2.y + 5)
        cr.stroke()

class MarkedLine(Primitive):
    def __init__(self, object_manager, points, fraction):
        super(MarkedLine, self).__init__(object_manager)
        self._points = points
        self._fraction = fraction

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        points = [
            Point.new(object_manager,
                      x + (i - 1) * 100,
                      y)
            for i in xrange(3)
        ]
        for point in points:
            object_manager.add_primitive(point, draw=True,
                                         check_overconstraints=False)
        return MarkedLine(object_manager, points, configuration)

    @classmethod
    def configure(cls, objects):
        dialog = gtk.Dialog("Horizontal distance")
        widget, entry_widgets = configuration_widget(
            [
                ("Fraction", float, "0.5"),
            ]
        )
        dialog.get_content_area().add(widget)
        dialog.add_button("Ok", 1)
        dialog.add_button("Cancel", 2)
        result = dialog.run()
        if result == 1:
            result = float(entry_widgets[0].get_text())
        else:
            result = False
        dialog.destroy()

        return result

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Fraction", float, self._fraction),
            ]
        )

    def reconfigure(self, widget, other_widgets):
        (fraction, ) = reconfigure(other_widgets)
        self._fraction = float(fraction)

    @classmethod
    def can_create(self, objects):
        return len(objects) == 0

    @property
    def p1(self):
        return self._points[0]

    @property
    def p2(self):
        return self._points[2]

    def draw(self, cr):
        if self.selected():
            cr.set_source_rgb(0.4, 0.4, 1)
            cr.set_line_width(0.5)
            cr.set_dash([2, 2], 2)
            cr.move_to(self.p1.x, self.p1.y)
            cr.line_to(self.p2.x, self.p2.y)
            cr.stroke()
        if self.active():
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 1, 0)
        cr.set_line_width(0.5)
        cr.set_dash([2, 2])
        cr.move_to(self.p1.x, self.p1.y)
        cr.line_to(self.p2.x, self.p2.y)
        cr.stroke()

    def constraints(self):
        return [
            ([(self._points[0].point(), 0, (1 - self._fraction)),
              (self._points[2].point(), 0, self._fraction),
              (self._points[1].point(), 0, -1),
            ], 0),
            ([(self._points[0].point(), (1 - self._fraction), 0),
              (self._points[2].point(), self._fraction, 0),
              (self._points[1].point(), -1, 0),
            ], 0),
        ]

    def children(self):
        return self._points

    def drag(self, offs_x, offs_y):
        '''
        Drag ourselves by a certain delta in the x and y directions.
        This will likely want to drag all children.
        '''
        for point in self._points:
            point.drag(offs_x, offs_y)

    def dist(self, p):
        def normalize(p):
            mag = p[0] * p[0] + p[1] * p[1]
            sqrtmag = math.sqrt(mag)
            return (p[0]/sqrtmag, p[1]/sqrtmag), sqrtmag
        v1, _ = normalize((p[0] - self.p1.x, p[1] - self.p1.y))
        v2, _ = normalize((p[0] - self.p2.x, p[1] - self.p2.y))
        v3_orig = (self.p2.x - self.p1.x, self.p2.y - self.p1.y)
        v3, v3mag = normalize(v3_orig)

        if v1[0] * v3[0] + v1[1] * v3[1] < 0:
            res = self._object_manager.point_dist(p, (self.p1.x, self.p1.y))
        elif v2[0] * v3[0] + v2[1] * v3[1] > 0:
            res = self._object_manager.point_dist(p, (self.p2.x, self.p2.y))
        else:
            res = abs(
                v3_orig[1] * p[0] - v3_orig[0] * p[1]
                + self.p2.x * self.p1.y - self.p2.y * self.p1.x
            ) / v3mag
            res = res * res

        if res < 10:
            return 10
        else:
            return res

    def to_dict(self):
        point_indices = [
            self._object_manager.primitive_idx(point)
            for point in self._points]
        return dict(
            points=point_indices,
            fraction=self._fraction,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        points = [object_manager.primitives[idx] for idx in dictionary['points']]
        return cls(object_manager, points, dictionary['fraction'])


class Array(Primitive):
    ELEMTYPE = None

    def __init__(self, object_manager, elements, nx, ny, numbering=None):
        super(Array, self).__init__(object_manager)
        self.elements = elements
        self.nx = nx
        self.ny = ny
        self.numbering=numbering

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        nx = configuration['nx']
        ny = configuration['ny']
        elemcfg = cls.ELEMTYPE.configure([])
        elements = []
        for i in range(nx):
            for j in range(ny):
                p = cls.ELEMTYPE.new(object_manager,
                                     x + (i - nx/2) * 30,
                                     y + (j - ny/2) * 30,
                                     elemcfg)

                elements.append(p)
                object_manager.add_primitive(p, constraining=False,
                                             check_overconstraints=False)

        return cls(object_manager, elements, nx, ny)

    @classmethod
    def can_create(cls, objects):
        return len(objects) == 0

    @classmethod
    def configure(cls, objects):
        dialog = gtk.Dialog("Enter dimensions")
        array = gtk.Table(2, 2)
        label1 = gtk.Label("# of elements (x): ")
        array.attach(label1, 0, 1, 0, 1)
        entry1 = gtk.Entry()
        array.attach(entry1, 1, 2, 0, 1)
        label1.show()
        entry1.show()
        label2 = gtk.Label("# of elements (y): ")
        array.attach(label2, 0, 1, 1, 2)
        entry2 = gtk.Entry()
        array.attach(entry2, 1, 2, 1, 2)
        label2.show()
        entry2.show()
        array.show()
        dialog.get_content_area().add(array)
        dialog.add_button("Ok", 1)
        dialog.add_button("Cancel", 2)
        result = dialog.run()
        if result == 1:
            x = int(entry1.get_text())
            y = int(entry2.get_text())
            result = dict(
                nx=x,
                ny=y,
            )
        else:
            result = False
        dialog.destroy()

        return result

    def reconfiguration_widget(self):
        def widget_for(numbering):
            fields = numbering.fields()
            if fields:
                table = gtk.Table(2, len(fields))
            else:
                table = gtk.VBox()
            widgetlist = []
            for idx, (fieldname, fieldtype, fielddefault) in enumerate(fields):
                fieldlabel = gtk.Label(fieldname + ": ")
                fieldlabel.show()
                if fieldtype == int or fieldtype == str:
                    fieldwidget = gtk.Entry()
                    if fielddefault is not None:
                        if fielddefault is NUMBER_CONST_WIDTH:
                            fieldwidget.set_text(str(self.nx))
                        elif fielddefault is NUMBER_CONST_HEIGHT:
                            fieldwidget.set_text(str(self.ny))
                        else:
                            fieldwidget.set_text(str(fielddefault))
                elif fieldtype == bool:
                    fieldwidget = gtk.ToggleButton("Enable")
                    if fielddefault is not None:
                        fieldwidget.set_active(fielddefault)
                else:
                    raise NotImplementedError("Type was %r" % (fieldtype, ))
                fieldwidget.show()
                table.attach(fieldlabel, 0, 1, idx, idx + 1)
                table.attach(fieldwidget, 1, 2, idx, idx + 1)

                widgetlist.append((fieldwidget, fieldtype))
            return table, widgetlist

        fields = [
            ("Clearance", int, self._clearance),
            ("Mask", int, self._mask),
        ]
        n = len(fields)

        reconfiguration_widget = gtk.Table(2, 2 + n)
        widgetlist = []
        for idx, (label, entry) in enumerate(configuration_widget_items(fields)):
            reconfiguration_widget.attach(label, 0, 1, idx, idx + 1)
            reconfiguration_widget.attach(entry, 1, 2, idx, idx + 1)

            widgetlist.append(entry)

        numbering_label = gtk.Label("Numbering: ")
        numbering_label.show()
        reconfiguration_widget.attach(numbering_label, 0, 1, n, n + 1)

        numbering_box = gtk.VBox()
        combo = gtk.combo_box_new_text()
        reconfiguration_widget.attach(combo, 1, 2, n, n + 1)
        reconfiguration_widget.attach(numbering_box, 0, 2, n + 1, n + 2)

        numbering_widgets = []
        for numbering_class, numbering_text in ALL_NUMBERINGS:
            # TODO: check that the numbering applies.
            if numbering_class.applies(self.nx, self.ny):
                combo.append_text(numbering_text)

                numbering_widgets.append((numbering_class, widget_for(numbering_class)))
        combo.set_active(0)
        combo.show()
        numbering_box.pack_start(combo, False, False, 0)
        for _, (numbering_widget, _) in numbering_widgets:
            numbering_box.add(numbering_widget)
        numbering_widgets[0][1][0].show()
        numbering_box.show()
        reconfiguration_widget.show()
        def changed_cb(cb):
            for idx, (_, (numbering_widget, _)) in enumerate(numbering_widgets):
                if cb.get_active() == idx:
                    numbering_widget.show()
                else:
                    numbering_widget.hide()

        combo.connect("changed", changed_cb)

        return reconfiguration_widget, (
            combo,
            numbering_widgets,
            widgetlist,
        )

    def reconfigure(self, widget, other_widgets):
        def get_value(ty, widget):
            if ty == str:
                return widget.get_text()
            elif ty == int:
                return int(widget.get_text()) # TODO: error checking?
            elif ty == bool:
                return widget.get_active()
        combobox, ALL_NUMBERINGS, reconf_widgetlist = other_widgets
        idx = combobox.get_active()
        numbering_class, (_, widgetlist) = ALL_NUMBERINGS[idx]
        print numbering_class, widgetlist
        vals = [
            get_value(ty, widget)
            for widget, ty in widgetlist
        ]
        self.numbering = numbering_class.new(
            self.nx, self.ny, vals
        )

        self._clearance, self._mask = reconfigure(reconf_widgetlist)

    def dependencies(self):
        return self.elements

    def children(self):
        return self.elements

    def draw(self, cr):
        for child in self.children():
            child.draw(cr)

    def p(self, i, j):
        return self.elements[j + self.ny * i]

    def constraints(self):
        all_constraints = []
        for child in self.children():
            all_constraints.extend(child.constraints())

        # Horizontal/vertical
        for i in range(0, min(self.nx, 2)):
            for j in range(0, self.ny - 1):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 1, 0),
                         (self.p(i, j + 1).center_point(), -1, 0),
                         ], 0),
                )

        for i in range(0, self.nx - 1):
            for j in range(0, min(self.ny, 2)):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 0, 1),
                         (self.p(i + 1, j).center_point(), 0, -1),
                         ], 0),
                )

        # Same distance
        for i in range(0, self.nx):
            for j in range(0, self.ny - 2):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 0, 1),
                         (self.p(i, j + 1).center_point(), 0, -2),
                         (self.p(i, j + 2).center_point(), 0, 1),
                         ], 0),
                )

        for i in range(0, self.nx - 2):
            for j in range(0, self.ny):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 1, 0),
                         (self.p(i + 1, j).center_point(), -2, 0),
                         (self.p(i + 2, j).center_point(), 1, 0),
                         ], 0),
                )

        # Same size
        p0_dimensions = self.p(0, 0).dimensions_to_constrain()
        for i in range(0, self.nx):
            for j in range(0, self.ny):
                if i == j == 0:
                    continue
                dims = self.p(i, j).dimensions_to_constrain(multiplier=-1)
                for (p0dims, pdims) in zip(p0_dimensions, dims):
                    all_constraints.append(
                        (p0dims + pdims, 0),
                    )

        return all_constraints

    def dist(self, p):
        return None
        dists = [child.dist(p) for child in self.children()]
        if any(dist for dist in dists if dist != None):
            return min(dist for dist in dists if dist != None)
        else:
            return None

    def drag(self, offs_x, offs_y):
        for child in self.children():
            child.drag(offs_x, offs_y)

    def to_dict(self):
        child_indices = [
            self._object_manager.primitive_idx(child)
            for child in self.children()]
        return dict(
            children=child_indices,
            deps=child_indices,
            nx=self.nx,
            ny=self.ny,
            numbering_type=self.numbering.TYPE() if self.numbering else None,
            numbering=self.numbering.to_dict(),
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        numbering_cls_id = dictionary['numbering_type']
        numbering_cls, _ = ALL_NUMBERINGS[numbering_cls_id]
        return cls(
            object_manager,
            [object_manager.primitives[child] for child in dictionary['children']],
            dictionary['nx'],
            dictionary['ny'],
            numbering_cls.from_dict(dictionary['numbering']),
        )

    def number_of(self, child):
        # TODO: find some better way to accomplish this.
        if not self.numbering:
            return None
        for i in xrange(self.nx):
            for j in xrange(self.ny):
                if child == self.p(i, j):
                    return self.numbering.number_of(i, j)

class PadArray(Array):
    ELEMTYPE = Pad

class BallArray(Array):
    ELEMTYPE = Ball

PRIMITIVE_TYPES = [
    None,
    Point,
    CenterPoint,
    Pad,
    Ball,
    Coincident,
    Horizontal,
    Vertical,
    HorizDistance,
    VertDistance,
    MarkedLine,
    PadArray,
    BallArray,
]
