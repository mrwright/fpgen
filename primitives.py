import pygtk
pygtk.require('2.0')
import gtk
import math

from constraint_utils import (
    constrain_ball,
    constrain_horiz,
    constrain_vert,
    equal_space_horiz,
    equal_space_vert,
)
from math_utils import (
    line_dist,
    point_dist,
)
from numbering import (
    ALL_NUMBERINGS,
    NUMBER_CONST_HEIGHT,
    NUMBER_CONST_WIDTH,
)
from ui_utils import (
    NumberEntry,
    StringEntry,
    UnitNumberEntry,
    configuration_widget,
    configuration_widget_items,
    reconfigure,
)
from units import UnitNumber

class Primitive(object):
    def __init__(self, object_manager, number=None, clearance=None, mask=None):
        self._clearance = clearance
        self._mask = mask
        self._object_manager = object_manager
        self._number = number

    @classmethod
    def new(cls, object_manager, x, y, configuration,
            draw=True, constraining=True, check_overconstraints=False):
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

    def draw(self, cr, active, selected):
        '''
        Draw this object using the given Cairo context.
        '''
        pass

    def delete(self):
        pass

    def drag(self, offs_x, offs_y):
        '''
        Drag ourselves by a certain delta in the x and y directions.
        This will likely want to drag all children.

        Returns whether or not we need to update point locations afterwards
        (which will generally be the case when points are dragged).
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
        # We don't have a number assigned directly, so fall back on asking
        # if the parent assigns a number to us.
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
    NAME = "Point"
    ZORDER = 0

    def __init__(self, object_manager, point):
        super(Point, self).__init__(object_manager)
        self.p = point

    @classmethod
    def new(cls, object_manager, x, y):
        point = object_manager.alloc_point(x, y)
        self = cls(object_manager, point)
        object_manager.add_primitive(
            self,
            check_overconstraints=False
        )
        return self

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
        return point_dist((self.x, self.y), p)

    def draw(self, cr, active, selected):
        if active:
            cr.set_source_rgb(1, 0, 0)

            cr.arc(self.x, self.y, 2, 0, 6.2)
            cr.fill()

        if selected:
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
        return True

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
    NAME = "Center point"

    def __init__(self, object_manager, point):
        super(CenterPoint, self).__init__(object_manager, point)

    @classmethod
    def new(cls, object_manager):
        point = object_manager.alloc_point(0, 0)
        object_manager.add_primitive(
            cls(object_manager, point),
            check_overconstraints=False
        )

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
        return False

    def can_delete(self):
        return False

class TileablePrimitive(Primitive):
    ZORDER = 1

    def dimensions_to_constrain(self):
        return []

    def center_point(self):
        return None

class Pad(TileablePrimitive):
    NAME = "Pad"

    def __init__(self, object_manager, points, number=None,
                 clearance=None, mask=None):
        super(Pad, self).__init__(object_manager, number, clearance, mask)
        self.points = points

    @classmethod
    def new(cls, object_manager, x, y, configuration,
            constraining=True):
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
        self = cls(object_manager, points)
        object_manager.add_primitive(
            self,
            constraining=constraining,
            check_overconstraints=False,
        )
        return self

    @classmethod
    def configure(cls, objects, w=100, h=100):
        # TODO: configuration dialog?
        return dict(w=w, h=h)

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Number", StringEntry(), self._number),
                ("Clearance", UnitNumberEntry(allow_empty=True),
                 self._clearance),
                ("Mask", UnitNumberEntry(allow_empty=True),
                 self._mask),
            ]
        ), None

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
        return self.point(x, y).point()

    def point(self, x, y):
        return self.points[x + 3 * y]

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
        constraints = []
        for j in xrange(3):
            constraints.extend(
                constrain_horiz([self.point(i, j) for i in xrange(3)])
            )
        for i in xrange(3):
            constraints.extend(
                constrain_vert([self.point(i, j) for j in xrange(3)])
            )

        # Spacing should be equal, in the horizontal and vertical directions.
        # (Note that this only needs to be applied to the first row/column;
        # the horizontal/vertical constraints take care of the rest.)
        constraints.extend(
            equal_space_horiz([self.point(0, 0),
                               self.point(1, 0),
                               self.point(2, 0)])
        )
        constraints.extend(
            equal_space_vert([self.point(0, 0),
                              self.point(0, 1),
                              self.point(0, 2)])
        )

        return constraints

    def draw(self, cr, active, selected):
        cr.save()
        if selected:
            cr.set_source_rgb(0, 0, 0.7)
        elif active:
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
        cr.restore()

    def drag(self, offs_x, offs_y):
        for point in self.points:
            point.drag(offs_x, offs_y)
        return True

    def dimensions_to_constrain(self, multiplier=1):
        # When in an array, we want the height and width of all pads to
        # be equal.
        return [[(self.p(0, 0), multiplier, 0),
                 (self.p(2, 0), -multiplier, 0)],
                [(self.p(0, 0), 0, multiplier),
                 (self.p(0, 2), 0, -multiplier)]]

    def center_point(self):
        return self.points[4]

    def to_dict(self):
        point_indices = [
            self._object_manager.primitive_idx(point)
            for point in self.points]
        return dict(
            points=point_indices,
            deps=point_indices,
            number=self._number,
            clearance=self._clearance.to_dict() if self._clearance else None,
            mask=self._mask.to_dict() if self._clearance else None,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        clearance = dictionary['clearance']
        mask = dictionary['mask']
        return cls(
            object_manager,
            [object_manager.primitives[idx]
             for idx in dictionary['points']],
            dictionary['number'],
            UnitNumber.from_dict(clearance) if clearance else None,
            UnitNumber.from_dict(mask) if mask else None
        )

class Pin(TileablePrimitive):
    NAME = "Pin"

    def __init__(self, object_manager, hole_points, ring_points,
                 center_point, number=None, clearance=None, mask=None):
        super(Pin, self).__init__(object_manager, number, clearance, mask)
        self._hole_points = hole_points
        self._ring_points = ring_points
        self._center_point = center_point

    @classmethod
    def new(cls, object_manager, x, y, configuration, hr=20, rr=40,
            constraining=True):
        # Five points: the center point, and four at the compass points
        # around it.
        center_point = Point.new(object_manager, x, y)
        hole_points = [
            Point.new(object_manager, x, y - hr/2),
            Point.new(object_manager, x - hr/2, y),
            Point.new(object_manager, x + hr/2, y),
            Point.new(object_manager, x, y + hr/2),
        ]
        ring_points = [
            Point.new(object_manager, x, y - rr/2),
            Point.new(object_manager, x - rr/2, y),
            Point.new(object_manager, x + rr/2, y),
            Point.new(object_manager, x, y + rr/2),
        ]
        self = cls(object_manager, hole_points, ring_points, center_point)
        object_manager.add_primitive(
            self,
            constraining=constraining,
            check_overconstraints=False,
        )
        return self

    @classmethod
    def configure(cls, objects):
        return None

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Number", StringEntry(), self._number),
                ("Clearance", UnitNumberEntry(allow_empty=True),
                 self._clearance),
                ("Mask", UnitNumberEntry(allow_empty=True),
                 self._mask),
            ]
        ), None

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
        return self._center_point.x

    @property
    def y(self):
        return self._center_point.y

    @property
    def hole_r(self):
        return self._hole_points[2].x - self._center_point.x

    @property
    def ring_r(self):
        return self._ring_points[2].x - self._center_point.x

    def children(self):
        return self._hole_points + self._ring_points + [self._center_point]

    def hp(self, x):
        return self._hole_points[x].point()

    def rp(self, x):
        return self._ring_points[x].point()

    def dist(self, p):
        # We consider the distance to us to be 10 to anywhere inside us,
        # and infinite to anywhere else.
        x, y = p[0], p[1]
        cx, cy = self.x, self.y
        r = self.ring_r
        if (x - cx) * (x - cx) + (y - cy) * (y - cy) < r * r:
            return 10
        else:
            return None

    def constraints(self):
        constraints = []
        # Points in a row should be aligned horizontally; points in a column
        # vertically.
        ring_points = (self._ring_points[:2]
                       + [self._center_point]
                       + self._ring_points[2:])
        hole_points = (self._hole_points[:2]
                       + [self._center_point]
                       + self._hole_points[2:])

        return constrain_ball(ring_points) + constrain_ball(hole_points)

    def draw(self, cr, active, selected):
        cr.save()
        if selected:
            cr.set_source_rgb(0, 0, 0.7)
        elif active:
            cr.set_source_rgb(0.7, 0, 0)
        else:
            cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.arc(self.x, self.y, self.ring_r, 0, 2 * math.pi)
        cr.fill()
        cr.restore()
        cr.save()
        cr.set_source_rgb(.9, .9, .9)
        cr.arc(self.x, self.y, self.hole_r, 0, 2 * math.pi)
        cr.fill()
        cr.restore()
        if self.number() is not None:
            cr.move_to(self.x, self.y)
            cr.show_text(self.number())
            cr.stroke()

    def drag(self, offs_x, offs_y):
        for point in self.children():
            point.drag(offs_x, offs_y)
        return True

    def dimensions_to_constrain(self, multiplier=1):
        # When in an array, we want the height and width of all pads
        # to be equal.
        return [
            [(self.rp(2), multiplier, 0),
             (self._center_point.point(), -multiplier, 0)],
            [(self.hp(2), multiplier, 0),
             (self._center_point.point(), -multiplier, 0)],
        ]

    def center_point(self):
        return self._center_point

    def to_dict(self):
        hole_point_indices = [
            self._object_manager.primitive_idx(point)
            for point in self._hole_points]
        ring_point_indices = [
            self._object_manager.primitive_idx(point)
            for point in self._ring_points]
        center_point_index = self._object_manager.primitive_idx(
            self._center_point
        )
        return dict(
            hole_points=hole_point_indices,
            ring_points=ring_point_indices,
            center_point=center_point_index,
            deps=hole_point_indices + ring_point_indices + [center_point_index],
            number=self._number,
            clearance=self._clearance.to_dict() if self._clearance else None,
            mask=self._mask.to_dict() if self._mask else None,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        clearance = dictionary['clearance']
        mask = dictionary['mask']
        return cls(
            object_manager,
            [object_manager.primitives[idx]
             for idx in dictionary['hole_points']],
            [object_manager.primitives[idx]
             for idx in dictionary['ring_points']],
            object_manager.primitives[dictionary['center_point']],
            dictionary['number'],
            UnitNumber.from_dict(clearance) if clearance else None,
            UnitNumber.from_dict(mask) if mask else None,
        )

class Ball(TileablePrimitive):
    NAME = "Ball"

    def __init__(self, object_manager, points, number=None,
                 clearance=None, mask=None, constraining=True):
        super(Ball, self).__init__(object_manager, number, clearance, mask)
        self.points = points

    @classmethod
    def new(cls, object_manager, x, y, configuration, r=20,
            draw=True, constraining=True, check_overconstraints=False):
        # Five points: the center point, and four at the compass points
        # around it.
        points = [
            Point.new(object_manager, x, y - r/2),
            Point.new(object_manager, x - r/2, y),
            Point.new(object_manager, x, y),
            Point.new(object_manager, x + r/2, y),
            Point.new(object_manager, x, y + r/2),
        ]
        self = cls(object_manager, points)
        object_manager.add_primitive(
            self,
            constraining=constraining,
            check_overconstraints=False,
        )
        return self

    @classmethod
    def configure(cls, objects):
        return None

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Number", StringEntry(), self._number),
                ("Clearance", UnitNumberEntry(allow_empty=True),
                 self._clearance),
                ("Mask", UnitNumberEntry(allow_empty=True),
                 self._mask),
            ]
        ), None

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
        return constrain_ball(self.points)

    def draw(self, cr, active, selected):
        cr.save()
        if selected:
            cr.set_source_rgb(0, 0, 0.7)
        elif active:
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

    def drag(self, offs_x, offs_y):
        for point in self.points:
            point.drag(offs_x, offs_y)
        return True

    def dimensions_to_constrain(self, multiplier=1):
        # When in an array, we want the height and width of all pads
        # to be equal.
        return [[(self.p(3), multiplier, 0),
                 (self.p(2), -multiplier, 0)]]

    def center_point(self):
        return self.points[2]

    def to_dict(self):
        point_indices = [
            self._object_manager.primitive_idx(point)
            for point in self.points]
        return dict(
            points=point_indices,
            deps=point_indices,
            number=self._number,
            clearance=self._clearance.to_dict() if self._clearance else None,
            mask=self._mask.to_dict() if self._mask else None,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        clearance = dictionary['clearance']
        mask = dictionary['mask']
        return cls(
            object_manager,
            [object_manager.primitives[idx]
             for idx in dictionary['points']],
            dictionary['number'],
            UnitNumber.from_dict(clearance) if clearance else None,
            UnitNumber.from_dict(mask) if mask else None,
        )

class TwoPointConstraint(Primitive):
    '''
    Base class for any constraint between two points.
    '''
    ZORDER = 1

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
        object_manager.add_primitive(
            cls(object_manager, objects),
            check_overconstraints=True
        )

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
                   [object_manager.primitives[idx]
                    for idx in dictionary['points']])

class Horizontal(TwoPointConstraint):
    NAME = "Horizontal constraint"

    def __init__(self, object_manager, objects):
        super(Horizontal, self).__init__(object_manager, objects)

    def constraints(self):
        return constrain_horiz([self.p1, self.p2])

    def dist(self, p):
        x, y = p[0], p[1]
        if self.p1.x < self.p2.x:
            p1, p2 = self.p1, self.p2
        else:
            p1, p2 = self.p2, self.p1
        if x < p1.x:
            return 10 + point_dist(p, (p1.x, p1.y))
        elif x > p2.x:
            return 10 + point_dist(p, (p2.x, p2.y))
        else:
            return 10 + (y - p1.y) * (y - p1.y)

    def draw(self, cr, active, selected):
        if selected:
            cr.set_source_rgb(0.4, 0.4, 1)
            cr.set_line_width(0.5)
            cr.set_dash([2, 2], 2)
            cr.move_to(self.p1.x, self.p1.y)
            cr.line_to(self.p2.x, self.p2.y)
            cr.stroke()
        if active:
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 1, 0)
        cr.set_line_width(0.5)
        cr.set_dash([2, 2])
        cr.move_to(self.p1.x, self.p1.y)
        cr.line_to(self.p2.x, self.p2.y)
        cr.stroke()


class Vertical(TwoPointConstraint):
    NAME = "Vertical constraint"

    def __init__(self, object_manager, objects):
        super(Vertical, self).__init__(object_manager, objects)

    def constraints(self):
        return constrain_vert([self.p1, self.p2])

    def dist(self, p):
        x, y = p[0], p[1]
        if self.p1.y < self.p2.y:
            p1, p2 = self.p1, self.p2
        else:
            p1, p2 = self.p2, self.p1
        if y < p1.y:
            return 10 + point_dist(p, (p1.x, p1.y))
        elif y > p2.y:
            return 10 + point_dist(p, (p2.x, p2.y))
        else:
            return 10 + (x - p1.x) * (x - p1.x)

    def draw(self, cr, active, selected):
        if selected:
            cr.set_source_rgb(0, 0, 1)
        elif active:
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
        object_manager.add_primitive(
            cls(object_manager, p1, p2, dist, 10),
            check_overconstraints=True
        )

    @classmethod
    def configure(cls, objects):
        if cls.horiz:
            dialog = gtk.Dialog("Horizontal distance")
        else:
            dialog = gtk.Dialog("Vertical distance")
        widget, entry_widgets = configuration_widget(
            [
                ("Distance",
                 UnitNumberEntry(allow_neg=False),
                 None),
            ]
        )
        dialog.get_content_area().add(widget)
        dialog.add_button("Ok", 1)
        dialog.add_button("Cancel", 2)
        entry1 = entry_widgets[0]
        while True:
            result = dialog.run()
            if result == 1:
                if not entry1.valid():
                    continue
                result = entry1.val()
            else:
                result = False
            break
        dialog.destroy()
        if not result:
            return False
        obj_list = list(objects)

        return dict(
            dist=result,
            p1=obj_list[0],
            p2=obj_list[1],
        )

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Distance",
                 UnitNumberEntry(allow_neg=True),
                 self.distance),
            ]
        ), None

    def reconfigure(self, widget, other_widgets):
        (self.distance, ) = reconfigure(other_widgets)

    def constraints(self):
        if self.horiz:
            return [
                ([(self.p2.point(), 1, 0), (self.p1.point(), -1, 0)],
                 self.distance.to("iu"))
            ]
        else:
            return [
                ([(self.p2.point(), 0, 1), (self.p1.point(), 0, -1)],
                 self.distance.to("iu"))
            ]

    def draw(self, cr, active, selected):
        if selected:
            cr.set_source_rgb(0, 0, 1)
        elif active:
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
            return point_dist(
                p,
                (self.p1.x,
                 self.p1.y + self.label_distance)
            )
        else:
            return point_dist(
                p,
                (self.p1.x + self.label_distance,
                 self.p2.y)
            )

    def drag(self, offs_x, offs_y):
        if self.horiz:
            self.label_distance += offs_y
        else:
            self.label_distance += offs_x
        return False

    def to_dict(self):
        dictionary = super(DistanceConstraint, self).to_dict()
        dictionary.update(dict(
            distance=self.distance.to_dict(),
            label_distance=self.label_distance,
        ))
        return dictionary

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        p1, p2 = tuple([object_manager.primitives[idx]
                        for idx in dictionary['points']])
        return cls(object_manager,
                   p1, p2,
                   UnitNumber.from_dict(dictionary['distance']),
                   dictionary['label_distance']
        )

class HorizDistance(DistanceConstraint):
    NAME = "Horizontal distance constraint"

    horiz = True

class VertDistance(DistanceConstraint):
    NAME = "Vertical distance constraint"

    horiz = False

class MeasuredDistance(TwoPointConstraint):
    def __init__(self, object_manager, p1, p2, label_dist):
        super(MeasuredDistance, self).__init__(object_manager, [p1, p2])

        self.p1 = p1
        self.p2 = p2
        self.label_distance = label_dist

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        objects = list(configuration['objects'])
        p1 = objects[0]
        p2 = objects[1]
        if cls.horiz and (p1.x > p2.x) or not cls.horiz and (p1.y > p2.y):
            p1, p2 = p2, p1
        object_manager.add_primitive(
            cls(object_manager, p1, p2, 100),
            check_overconstraints=True
        )

    def reconfiguration_widget(self):
        return None

    def constraints(self):
        return []

    def draw(self, cr, active, selected):
        if selected:
            cr.set_source_rgb(0, 0, 1)
        elif active:
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
            cr.line_to(self.p2.x, self.p1.y + self.label_distance)
            cr.stroke()
        else:
            cr.move_to(self.p1.x + self.label_distance, self.p2.y)
            cr.line_to(self.p1.x + self.label_distance, self.p1.y)
            cr.stroke()
        # TODO: arrowheads

    @property
    def x(self):
        if self.horiz:
            return (self.p1.x + self.p2.x)/2
        else:
            return self.p1.x + self.label_distance

    @property
    def y(self):
        if self.horiz:
            return self.p1.y + self.label_distance
        else:
            return (self.p1.y + self.p2.y)/2

    def dist(self, p):
        if self.horiz:
            return line_dist(
                self.p1.x, self.p1.y + self.label_distance,
                self.p2.x, self.p1.y + self.label_distance,
                p[0], p[1])
        else:
            return line_dist(
                self.p1.x + self.label_distance, self.p1.y,
                self.p1.x + self.label_distance, self.p2.y,
                p[0], p[1])

    def drag(self, offs_x, offs_y):
        if self.horiz:
            self.label_distance += offs_y
        else:
            self.label_distance += offs_x
        return False

    def to_dict(self):
        dictionary = super(MeasuredDistance, self).to_dict()
        dictionary.update(dict(
            label_distance=self.label_distance,
        ))
        return dictionary

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        p1, p2 = tuple([object_manager.primitives[idx]
                        for idx in dictionary['points']])
        return cls(object_manager,
                   p1, p2,
                   dictionary['label_distance']
        )

    def dimensions_to_constrain(self, multiplier=1):
        raise NotImplementedError()

class MeasuredHorizDistance(MeasuredDistance):
    horiz = True

    NAME = "Measured horizontal distance"

    def dimensions_to_constrain(self, multiplier=1):
        return [[(self.p1.point(), -multiplier, 0),
                 (self.p2.point(), multiplier, 0)]]

class MeasuredVertDistance(MeasuredDistance):
    horiz = False

    NAME = "Measured vertical distance"

    def dimensions_to_constrain(self, multiplier=1):
        return [[(self.p1.point(), 0, -multiplier),
                 (self.p2.point(), 0, multiplier)]]


class SameDistance(Primitive):
    ZORDER = 1

    NAME = "Same distance constraint"

    def __init__(self, object_manager, constrained_object, equiv_class_id,
                 is_representative):
        super(SameDistance, self).__init__(object_manager, [constrained_object])
        self._constrained_object = constrained_object
        self._equiv_class_id = equiv_class_id
        self._is_representative = is_representative

    @classmethod
    def rename_class(cls, object_manager, from_class, to_class):
        clsdata = object_manager.clsdata[cls]
        for primitive in clsdata['samedist_primitives']:
            if primitive._equiv_class_id == from_class:
                primitive._equiv_class_id = to_class
                if from_class != to_class:
                    primitive._is_representative = False
        classes = clsdata['equiv_classes']
        classes.remove(from_class)
        classes.add(to_class)

    @classmethod
    def squash_classes(cls, object_manager):
        clsdata = object_manager.clsdata[cls]
        classes = clsdata['equiv_classes']
        numclasses = len(classes)
        rename_dict = {}
        for c in classes:
            if c < numclasses:
                rename_dict[c] = c

        for c in classes:
            if c >= numclasses:
                for i in xrange(numclasses):
                    if i not in rename_dict:
                        rename_dict[i] = c

        for to_class, from_class in rename_dict.iteritems():
            cls.rename_class(object_manager, from_class, to_class)

    @classmethod
    def new(cls, object_manager, x, y, configuration):
        if cls not in object_manager.clsdata:
            object_manager.clsdata[cls] = dict(
                # Note: an optimization we could do here is have this be a
                # map from the class number to the set of members, but that
                # doesn't seem worthwhile.
                equiv_classes=set(),
                samedist_primitives=set()
            )
        clsdata = object_manager.clsdata[cls]
        equiv_classes = clsdata['equiv_classes']

        objects = set(configuration)

        other_distance_primitives = clsdata['samedist_primitives']
        classes_to_merge = set()
        for primitive in other_distance_primitives:
            remove = False
            for obj in objects:
                if obj is primitive._constrained_object:
                    classes_to_merge.add(primitive._equiv_class_id)
                    remove = True
                    break
            if remove:
                objects.remove(obj)
        # At this point, "objects" contains only those objects that
        # still need an equivalence class and weren't already part of one.

        if len(classes_to_merge) == 0:
            # No existing classes; we can assign a new one.
            equiv_class = len(equiv_classes)
            equiv_classes.add(equiv_class)
            represented = False
        elif len(classes_to_merge) >= 1:
            equiv_class = min(classes_to_merge)
            classes_to_merge.remove(equiv_class)
            for from_class in classes_to_merge:
                cls.rename_class(object_manager, from_class, equiv_class)
            cls.squash_classes(object_manager)
            represented = True

        added_primitives = []

        for obj in objects:
            sd = cls(object_manager, obj, equiv_class, not represented)
            represented = True
            object_manager.add_primitive(sd, check_overconstraints=True)
            # TODO: recover from the situation where we overconstrain.
            other_distance_primitives.add(sd)

        for obj in other_distance_primitives:
            print obj._equiv_class_id, obj._is_representative

    @classmethod
    def configure(cls, objects):
        return objects

    @classmethod
    def can_create(cls, objects):
        return len(objects) > 1 and all(isinstance(obj, MeasuredDistance)
                                        for obj in objects)

    def dependencies(self):
        return [self._constrained_object]

    def delete(self):
        clsdata = self._object_manager.clsdata[type(self)]
        other_primitives = clsdata['samedist_primitives']
        classes = clsdata['equiv_classes']
        other_primitives.remove(self)

        other_count = 0
        other_primitive = None
        for primitive in other_primitives:
            if primitive._equiv_class_id == self._equiv_class_id:
                other_count += 1
                other_primitive = primitive
        if other_count == 0:
            classes.remove(self._equiv_class_id)
            self.squash_classes(self._object_manager)
        elif other_count == 1:
            self._object_manager.delete_primitive(other_primitive)
            # Note: the above deletion will also remove the class from the list.
        elif self._is_representative:
            other_primitive._is_representative = True

    @property
    def x(self):
        obj = self._constrained_object
        return obj.x

    @property
    def y(self):
        obj = self._constrained_object
        return obj.y

    def dist(self, p):
        d = point_dist(p, (self.x, self.y))
        if d < 10:
            return 0
        else:
            return d + 1

    def draw(self, cr, active, selected):
        obj = self._constrained_object
        clsid = self._equiv_class_id
        if selected:
            cr.set_source_rgb(0, 0, 1)
        elif active:
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(0.3)
        for c in xrange(clsid + 1):
            if obj.horiz:
                x = obj.x - (clsid / 2. - c) * 1.5
                y = obj.y
            else:
                x = obj.x
                y = obj.y - (clsid / 2. - c) * 1.5
            cr.move_to(x - 2, y - 2)
            cr.line_to(x + 2, y + 2)
            cr.stroke()

    def constraints(self):
        if not self._is_representative:
            return []

        clsdata = self._object_manager.clsdata[type(self)]
        constraints = []
        thesedims = self._constrained_object.dimensions_to_constrain()
        for primitive in clsdata['samedist_primitives']:
            if (primitive._equiv_class_id == self._equiv_class_id and
                primitive is not self):
                dims = primitive._constrained_object.dimensions_to_constrain(
                    multiplier=-1
                )
                for (thiscons, othercons) in zip(thesedims, dims):
                    constraints.append(
                        (thiscons + othercons, 0),
                    )

        return constraints

    def to_dict(self):
        constrained_object_idx = self._object_manager.primitive_idx(
            self._constrained_object
        )
        return dict(
            constrained_object=constrained_object_idx,
            equiv_class_id=self._equiv_class_id,
            is_representative=self._is_representative,
            deps=[constrained_object_idx],
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        constrained_object = object_manager.primitives[
            dictionary['constrained_object']
        ]
        self = cls(
            object_manager,
            constrained_object,
            dictionary['equiv_class_id'],
            dictionary['is_representative'],
        )
        if cls not in object_manager.clsdata:
            object_manager.clsdata[cls] = dict(
                equiv_classes=set(),
                samedist_primitives=set()
            )
        clsdata = object_manager.clsdata[cls]
        clsdata['equiv_classes'].add(self._equiv_class_id)
        clsdata['samedist_primitives'].add(self)
        return self

class Coincident(TwoPointConstraint):
    NAME = "Coincident constraint"

    def __init__(self, object_manager, objects):
        super(Coincident, self).__init__(object_manager, objects)

    def constraints(self):
        return (constrain_horiz([self.p1, self.p2]) +
                constrain_vert([self.p1, self.p2]))

    def dist(self, p):
        dist = point_dist(
            p, (self.p1.x, self.p1.y))
        if dist < 10:
            return dist + 1
        else:
            return dist - 1

    def draw(self, cr, active, selected):
        if active:
            cr.set_source_rgb(1, 0, 0)
        elif selected:
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

class DrawnLine(Primitive):
    NAME = "Line"
    ZORDER = 1
    HORIZONTAL = False
    VERTICAL = False

    def __init__(self, object_manager, p1points, p2points, centerpoints,
                 thickness=None):
        super(DrawnLine, self).__init__(object_manager)
        self._p1points = p1points
        self._p2points = p2points
        self._centerpoints = centerpoints
        self._thickness = thickness

    @classmethod
    def new(cls, object_manager, x, y, configuration,
            draw=True, constraining=True, check_overconstraints=False):
        specified_thickness = configuration['thickness']
        if specified_thickness:
            thickness = specified_thickness.to("iu")
        else:
            thickness = 10
        if cls.VERTICAL:
            xoffs = 0
            yoffs = 100
        else:
            xoffs = 100
            yoffs = 0
        p1points = [
            Point.new(object_manager,
                      x - xoffs +  0,        y - yoffs - thickness),
            Point.new(object_manager,
                      x - xoffs - thickness, y - yoffs + 0),
            Point.new(object_manager,
                      x - xoffs +         0, y - yoffs + 0),
            Point.new(object_manager,
                      x - xoffs + thickness, y - yoffs + 0),
            Point.new(object_manager,
                      x - xoffs +         0, y - yoffs + thickness),
        ]
        p2points = [
            Point.new(object_manager,
                      x + xoffs +         0, y + yoffs - thickness),
            Point.new(object_manager,
                      x + xoffs - thickness, y + yoffs + 0),
            Point.new(object_manager,
                      x + xoffs +         0, y + yoffs + 0),
            Point.new(object_manager,
                      x + xoffs + thickness, y + yoffs + 0),
            Point.new(object_manager,
                      x + xoffs +         0, y + yoffs + thickness),
        ]
        if cls.HORIZONTAL:
            centerpoints = [
                Point.new(object_manager, x, y - thickness),
                Point.new(object_manager, x, y + 0),
                Point.new(object_manager, x, y + thickness),
            ]
        elif cls.VERTICAL:
            centerpoints = [
                Point.new(object_manager, x - thickness, y),
                Point.new(object_manager, x +         0, y),
                Point.new(object_manager, x + thickness, y),
            ]
        else:
            centerpoints = []

        object_manager.add_primitive(
            cls(object_manager, p1points, p2points, centerpoints,
                specified_thickness),
            check_overconstraints=False
        )

    @classmethod
    def configure(cls, objects):
        dialog = gtk.Dialog("Enter dimensions")
        widget, entry_widgets = configuration_widget(
            [
                ("Thickness",
                 UnitNumberEntry(allow_neg=False, allow_empty=True),
                 None),
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
                thickness_entry = entry_widgets[0]
                thickness = thickness_entry.val()
                result = dict(
                    thickness=thickness,
                )
            else:
                result = False
            break
        dialog.destroy()

        return result

    def reconfiguration_widget(self):
        print self._thickness
        if self._thickness is not None:
            return configuration_widget(
                [
                    ("Thickness",
                     UnitNumberEntry(allow_neg=False, allow_empty=False),
                     self._thickness),
                ]
            ), None
        else:
            return None

    def reconfigure(self, widget, other_widgets):
        (self._thickness, ) = reconfigure(other_widgets)

    @classmethod
    def placeable(cls):
        return True

    @classmethod
    def can_create(cls, objects):
        return not objects

    def children(self):
        return self._p1points + self._p2points + self._centerpoints

    @property
    def x1(self):
        return self._p1points[2].x

    @property
    def y1(self):
        return self._p1points[2].y

    @property
    def x2(self):
        return self._p2points[2].x

    @property
    def y2(self):
        return self._p2points[2].y

    @property
    def thickness(self):
        return self._p1points[2].y - self._p1points[0].y

    def dist(self, p):
        res = line_dist(self.x1, self.y1, self.x2, self.y2, p[0], p[1])

        if res < self.thickness * self.thickness:
            return 10
        else:
            return res

    def constraints(self):
        constraints = []
        constraints.extend(constrain_ball(self._p1points))
        constraints.extend(constrain_ball(self._p2points))

        if self.HORIZONTAL:
            constraints.extend(
                constrain_vert(self._centerpoints) +
                equal_space_vert(self._centerpoints) +
                constrain_horiz([self._p1points[0],
                                 self._centerpoints[0]]) +
                constrain_horiz([self._p1points[2],
                                 self._centerpoints[1],
                                 self._p2points[2]]) +
                equal_space_horiz([self._p1points[2],
                                   self._centerpoints[1],
                                   self._p2points[2]])
            )
        elif self.VERTICAL:
            constraints.extend(
                constrain_horiz(self._centerpoints) +
                equal_space_horiz(self._centerpoints) +
                constrain_vert([self._p1points[0],
                                self._centerpoints[0]]) +
                constrain_vert([self._p1points[2],
                                 self._centerpoints[1],
                                 self._p2points[2]]) +
                equal_space_vert([self._p1points[2],
                                   self._centerpoints[1],
                                   self._p2points[2]])
            )

        constraints.append(
            ([(self._p1points[0].point(), 0, 1),
              (self._p1points[2].point(), 0, -1),
              (self._p2points[0].point(), 0, -1),
              (self._p2points[2].point(), 0, 1)], 0)
        )

        if self._thickness:
            constraints.append(
                ([(self._p1points[2].point(), 0, 1),
                  (self._p1points[0].point(), 0, -1)], self._thickness.to("iu"))
            )

        return constraints

    def draw(self, cr, active, selected):
        cr.save()
        if active:
            cr.set_source_rgb(1, 0, 0)
        elif selected:
            # TODO: if both are the case.
            cr.set_source_rgb(0.4, 0.4, 1)
        else:
            cr.set_source_rgb(0, 1, 0)

        cr.set_line_width(self.thickness * 2)
        cr.move_to(self.x1, self.y1)
        cr.line_to(self.x2, self.y2)
        cr.stroke()
        cr.arc(self.x1, self.y1, self.thickness, 0, 2 * math.pi)
        cr.fill()
        cr.arc(self.x2, self.y2, self.thickness, 0, 2 * math.pi)
        cr.fill()
        cr.restore()

    def drag(self, offs_x, offs_y):
        for point in self.children():
            point.drag(offs_x, offs_y)
        return True

    def to_dict(self):
        p1_indices, p2_indices = (
            [
                self._object_manager.primitive_idx(point)
                for point in points
            ]
            for points in (self._p1points, self._p2points)
        )
        center_indices = [
            self._object_manager.primitive_idx(point)
            for point in self._centerpoints
        ] if self._centerpoints else None
        return dict(
            p1points=p1_indices,
            p2points=p2_indices,
            centerpoints=center_indices,
            thickness=self._thickness.to_dict() if self._thickness else None,
            deps=p1_indices+p2_indices+center_indices,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        p1points, p2points = (
            # TODO: helper function for serializing lists of points.
            [
                object_manager.primitives[idx]
                for idx in points
            ]
            for points in (dictionary['p1points'], dictionary['p2points'])
        )
        centerpoints = [
            object_manager.primitives[idx]
            for idx in dictionary['centerpoints']
        ] if dictionary['centerpoints'] else None
        thickness = (UnitNumber.from_dict(dictionary['thickness'])
                     if dictionary['thickness'] else None)
        return cls(object_manager, p1points, p2points, centerpoints, thickness)

class HorizontalDrawnLine(DrawnLine):
    HORIZONTAL = True

class VerticalDrawnLine(DrawnLine):
    VERTICAL = True

class MarkedLine(Primitive):
    NAME = "Marked line"
    ZORDER = 1

    def __init__(self, object_manager, points, fraction):
        super(MarkedLine, self).__init__(object_manager)
        self._points = points
        self._fraction = fraction

    @classmethod
    def new(cls, object_manager, x, y, configuration,
            draw=True, constraining=True, check_overconstraints=False):
        points = [
            Point.new(object_manager,
                      x + (i - 1) * 100,
                      y)
            for i in xrange(3)
        ]
        object_manager.add_primitive(
            cls(object_manager, points, configuration),
            check_overconstraints=False
        )

    @classmethod
    def configure(cls, objects):
        dialog = gtk.Dialog("Horizontal distance")
        widget, entry_widgets = configuration_widget(
            [
                # TODO: allow it to be clamped between 0 and 1.
                ("Fraction", NumberEntry(float,
                                         allow_neg=False,
                                         allow_zero=True,
                                         max_val=1), "0.5"),
            ]
        )
        dialog.get_content_area().add(widget)
        dialog.add_button("Ok", 1)
        dialog.add_button("Cancel", 2)
        while True:
            result = dialog.run()
            if result == 1:
                if not entry_widgets[0].valid():
                    continue
                result = entry_widgets[0].val()
            else:
                result = False
            break
        dialog.destroy()

        return result

    def reconfiguration_widget(self):
        return configuration_widget(
            [
                ("Fraction", NumberEntry(float,
                                         allow_neg=False,
                                         allow_zero=True,
                                         max_val=1), self._fraction),
            ]
        ), None

    def reconfigure(self, widget, other_widgets):
        (self._fraction, ) = reconfigure(other_widgets)

    @classmethod
    def can_create(self, objects):
        return len(objects) == 0

    @property
    def p1(self):
        return self._points[0]

    @property
    def p2(self):
        return self._points[2]

    def draw(self, cr, active, selected):
        if selected:
            cr.set_source_rgb(0.4, 0.4, 1)
            cr.set_line_width(0.5)
            cr.set_dash([2, 2], 2)
            cr.move_to(self.p1.x, self.p1.y)
            cr.line_to(self.p2.x, self.p2.y)
            cr.stroke()
        if active:
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
        for point in self._points:
            point.drag(offs_x, offs_y)
        return True

    def dist(self, p):
        res = line_dist(self.p1.x, self.p1.y, self.p2.x, self.p2.y, p[0], p[1])

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
            deps=point_indices,
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        points = [object_manager.primitives[idx]
                  for idx in dictionary['points']]
        return cls(object_manager, points, dictionary['fraction'])


class Array(Primitive):
    ELEMTYPE = None
    ZORDER = 3

    def __init__(self, object_manager, elements, nx, ny, centerpoint,
                 numbering=None):
        super(Array, self).__init__(object_manager)
        self.elements = elements
        self.nx = nx
        self.ny = ny
        self.numbering = numbering
        self.centerpoint = centerpoint

    @classmethod
    def new(cls, object_manager, x, y, configuration,
            draw=True, constraining=True, check_overconstraints=False):
        nx = configuration['nx']
        ny = configuration['ny']
        elemcfg = cls.ELEMTYPE.configure([])
        elements = []
        for i in range(nx):
            for j in range(ny):
                p = cls.ELEMTYPE.new(object_manager,
                                     x + (i - nx/2) * 30,
                                     y + (j - ny/2) * 30,
                                     elemcfg,
                                     constraining=False)

                elements.append(p)

        if (nx%2 == 0) or (ny%2 == 0):
            # If either dimension is even, add a center point
            p = Point.new(object_manager, x, y)
            centerpoint = p
        else:
            centerpoint = None

        object_manager.add_primitive(
            cls(object_manager, elements, nx, ny, centerpoint),
            check_overconstraints=False,
        )

    @classmethod
    def can_create(cls, objects):
        return len(objects) == 0

    @classmethod
    def configure(cls, objects):
        dialog = gtk.Dialog("Enter dimensions")
        widget, entry_widgets = configuration_widget(
            [
                ("# of elements (x)",
                 NumberEntry(int, allow_neg=False, allow_zero=False),
                 None),
                ("# of elements (y)",
                 NumberEntry(int, allow_neg=False, allow_zero=False),
                 None),
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
                entry1, entry2 = tuple(entry_widgets)
                x = entry1.val()
                y = entry2.val()
                result = dict(
                    nx=x,
                    ny=y,
                )
            else:
                result = False
            break
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
            for idx, (fieldname, fieldwidget, fielddefault
            ) in enumerate(fields):
                fieldlabel = gtk.Label(fieldname + ": ")
                fieldlabel.show()
                if fielddefault is not None:
                    if fielddefault is NUMBER_CONST_WIDTH:
                        fieldwidget.set_val(self.nx)
                    elif fielddefault is NUMBER_CONST_HEIGHT:
                            fieldwidget.set_val(self.ny)
                    else:
                        fieldwidget.set_val(fielddefault)
                fieldwidget.show()
                table.attach(fieldlabel, 0, 1, idx, idx + 1)
                table.attach(fieldwidget, 1, 2, idx, idx + 1)

                widgetlist.append(fieldwidget)
            return table, widgetlist

        fields = [
            ("Clearance", UnitNumberEntry(allow_empty=True), self._clearance),
            ("Mask", UnitNumberEntry(allow_empty=True), self._mask),
        ]
        n = len(fields)

        reconfiguration_widget = gtk.Table(2, 2 + n)
        widgetlist = []
        for idx, (label, entry) in enumerate(
                configuration_widget_items(fields)):
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

                numbering_widgets.append((numbering_class,
                                          widget_for(numbering_class)))
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

        return (reconfiguration_widget, (
            combo,
            numbering_widgets,
            widgetlist,
        )), lambda : True

    def reconfigure(self, _, other_widgets):
        combobox, ALL_NUMBERINGS, reconf_widgetlist = other_widgets
        idx = combobox.get_active()
        numbering_class, (_, widgetlist) = ALL_NUMBERINGS[idx]
        print numbering_class, widgetlist
        vals = [
            widget.val() for widget in widgetlist
        ]
        self.numbering = numbering_class.new(
            self.nx, self.ny, vals
        )

        self._clearance, self._mask = reconfigure(reconf_widgetlist)

    def dependencies(self):
        return self.elements + ([self.centerpoint]
                                if self.centerpoint is not None else [])

    def children(self):
        return self.elements + ([self.centerpoint]
                                if self.centerpoint is not None else [])

    def draw(self, cr, active, selected):
        pass

    def p(self, i, j):
        return self.elements[j + self.ny * i]

    def constraints(self):
        all_constraints = []
        for child in self.children():
            all_constraints.extend(child.constraints())

        # Horizontal/vertical
        for i in range(0, min(self.nx, 2)):
            all_constraints.extend(
                constrain_vert([self.p(i, j).center_point()
                                for j in xrange(self.ny)]))

        for j in range(0, min(self.ny, 2)):
            all_constraints.extend(
                constrain_horiz([self.p(i, j).center_point()
                                 for i in xrange(self.nx)]))

        # Same distance
        for i in range(0, self.nx):
            all_constraints.extend(
                equal_space_vert([self.p(i, j).center_point()
                                   for j in xrange(self.ny)]))

        for j in range(0, self.ny):
            all_constraints.extend(
                equal_space_horiz([self.p(i, j).center_point()
                                   for i in xrange(self.nx)]))

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

        if self.centerpoint is not None:
            if self.nx > 1:
                all_constraints.extend(
                    equal_space_horiz(
                        [self.p(0, 0).center_point(),
                         self.centerpoint,
                         self.p(self.nx - 1, 0).center_point()]
                    )
                )
            else:
                all_constraints.extend(
                    constrain_vert(
                        [self.p(0, 0).center_point(),
                         self.centerpoint.point()]
                    )
                )

            if self.ny > 1:
                all_constraints.extend(
                    equal_space_vert(
                        [self.p(0, 0).center_point(),
                         self.centerpoint,
                         self.p(0, self.ny - 1).center_point()]
                    )
                )
            else:
                all_constraints.extend(
                    constrain_horiz(
                        [self.p(0, 0).center_point(),
                         self.centerpoint]
                    )
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
        return True

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
            numbering=self.numbering.to_dict() if self.numbering else None,
            centerpoint=(self._object_manager.primitive_idx(self.centerpoint)
                         if self.centerpoint is not None else None),
        )

    @classmethod
    def from_dict(cls, object_manager, dictionary):
        numbering_cls_id = dictionary['numbering_type']
        numbering_cls, _ = (ALL_NUMBERINGS[numbering_cls_id]
                            if numbering_cls_id else (None, None))
        centerpoint_idx = dictionary['centerpoint']
        return cls(
            object_manager,
            [object_manager.primitives[child]
             for child in dictionary['children']],
            dictionary['nx'],
            dictionary['ny'],
            (object_manager.primitives[centerpoint_idx]
             if centerpoint_idx is not None else None),
            numbering_cls.from_dict(dictionary['numbering'])
                if numbering_cls else None,
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
    NAME = "Pad array"
    ELEMTYPE = Pad

class PinArray(Array):
    NAME = "Pin array"
    ELEMTYPE = Pin

class BallArray(Array):
    NAME = "Ball array"
    ELEMTYPE = Ball

PRIMITIVE_TYPES = [
    None,
    Point,
    CenterPoint,
    Pad,
    Pin,
    Ball,
    Coincident,
    DrawnLine,
    HorizontalDrawnLine,
    VerticalDrawnLine,
    Horizontal,
    Vertical,
    HorizDistance,
    VertDistance,
    MarkedLine,
    PadArray,
    PinArray,
    BallArray,
    MeasuredHorizDistance,
    MeasuredVertDistance,
    SameDistance,
]
