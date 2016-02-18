import pygtk
pygtk.require('2.0')
import gtk
import math


class Primitive(object):
    def __init__(self, object_manager):
        self._active = False
        self._selected = False
        self._object_manager = object_manager

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


class Point(Primitive):
    '''
    This class wraps the ObjectManager's points.
    '''
    def __init__(self, object_manager, x, y):
        super(Point, self).__init__(object_manager)
        self.p = object_manager.alloc_point(x, y)

    def x(self):
        return self._object_manager.point_x(self.p)

    def y(self):
        return self._object_manager.point_y(self.p)

    def point(self):
        '''
        Return the index of this point in the ObjectManager.
        '''
        return self.p

    def dist(self, p):
        return self._object_manager.point_dist((self.x(), self.y()), p)

    def draw(self, cr):
        if self.active():
            cr.set_source_rgb(1, 0, 0)

            cr.arc(self.x(), self.y(), 2, 0, 6.2)
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
        # TODO: remove our point from all structures.
        pass


class CenterPoint(Point):
    def __init__(self, object_manager, objects):
        assert self.can_create(objects)
        super(CenterPoint, self).__init__(object_manager, 0, 0)

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

class TileablePrimitive(Primitive):
    def dimensions_to_constrain(self):
        return []

    def center_point(self):
        return None

class Pad(TileablePrimitive):
    def __init__(self, object_manager, x, y, w, h):
        # Pads consist of 9 points, evenly spaced in a 3x3 grid.
        super(Pad, self).__init__(object_manager)
        self.points = []
        for j in range(3):
            for i in range(3):
                self.points.append(
                    Point(object_manager,
                          x + (i - 1) * w/2,
                          y + (j - 1) * h/2)
                )
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        for point in self.points:
            self._object_manager.add_primitive(point, draw=False,
                                               check_overconstraints=False)

    def children(self):
        return self.points

    def p(self, x, y):
        return self.points[x + 3 * y].point()

    def dist(self, p):
        # We consider the distance to us to be 10 to anywhere inside us,
        # and infinite to anywhere else. This ensures we'll only be active
        # when the mouse is actually on the pad, but that individual points
        # in us can still be active, too.
        x, y = p[0], p[1]
        x0 = min(self.points[0].x(), self.points[8].x())
        x1 = max(self.points[0].x(), self.points[8].x())
        y0 = min(self.points[0].y(), self.points[8].y())
        y1 = max(self.points[0].y(), self.points[8].y())
        if x > x0 and x < x1 and y > y0 and y < y1:
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
        if self.selected():
            cr.set_source_rgb(0, 0, 0.7)
        elif self.active():
            cr.set_source_rgb(0.7, 0, 0)
        else:
            cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.rectangle(self.points[0].x(),
                     self.points[0].y(),
                     self.points[8].x() - self.points[0].x(),
                     self.points[8].y() - self.points[0].y())
        cr.fill()
        cr.save()
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

class Ball(TileablePrimitive):
    def __init__(self, object_manager, x, y, r):
        # Five points: the center point, and four at the compass points around it.
        super(Ball, self).__init__(object_manager)
        self.points = [
            Point(object_manager, x, y - r/2),
            Point(object_manager, x - r/2, y),
            Point(object_manager, x, y),
            Point(object_manager, x + r/2, y),
            Point(object_manager, x, y + r/2),
        ]
        self.x = x
        self.y = y
        self.r = r
        for point in self.points:
            self._object_manager.add_primitive(point, draw=False,
                                               check_overconstraints=False)

    def children(self):
        return self.points

    def p(self, x):
        return self.points[x].point()

    def dist(self, p):
        # We consider the distance to us to be 10 to anywhere inside us,
        # and infinite to anywhere else.
        x, y = p[0], p[1]
        cx, cy = self.points[2].x(), self.points[2].y()
        r = self.points[3].x() - self.points[2].x()
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
        if self.selected():
            cr.set_source_rgb(0, 0, 0.7)
        elif self.active():
            cr.set_source_rgb(0.7, 0, 0)
        else:
            cr.set_source_rgb(0.7, 0.7, 0.7)
        cr.arc(self.points[2].x(),
               self.points[2].y(),
               self.points[3].x() - self.points[2].x(),
               0, 2 * math.pi
        )
        cr.fill()
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

    def dependencies(self):
        return [self.p1, self.p2]

    @classmethod
    def can_create(cls, objects):
        return len(objects) == 2 and all(isinstance(o, Point) for o in objects)


class Horizontal(TwoPointConstraint):
    def constraints(self):
        return [
            ([(self.p1.point(), 0, 1), (self.p2.point(), 0, -1)], 0)
        ]

    def dist(self, p):
        x, y = p[0], p[1]
        if self.p1.x() < self.p2.x():
            p1, p2 = self.p1, self.p2
        else:
            p1, p2 = self.p2, self.p1
        if x < p1.x():
            return 10 + self._object_manager.point_dist(p, (p1.x(), p1.y()))
        elif x > p2.x():
            return 10 + self._object_manager.point_dist(p, (p2.x(), p2.y()))
        else:
            return 10 + (y - p1.y()) * (y - p1.y())

    def draw(self, cr):
        if self.selected():
            cr.set_source_rgb(0.4, 0.4, 1)
            cr.set_line_width(0.5)
            cr.set_dash([2, 2], 2)
            cr.move_to(self.p1.x(), self.p1.y())
            cr.line_to(self.p2.x(), self.p2.y())
            cr.stroke()
        if self.active():
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 1, 0)
        cr.set_line_width(0.5)
        cr.set_dash([2, 2])
        cr.move_to(self.p1.x(), self.p1.y())
        cr.line_to(self.p2.x(), self.p2.y())
        cr.stroke()


class Vertical(TwoPointConstraint):
    def constraints(self):
        return [
            ([(self.p1.point(), 1, 0), (self.p2.point(), -1, 0)], 0)
        ]

    def dist(self, p):
        x, y = p[0], p[1]
        if self.p1.y() < self.p2.y():
            p1, p2 = self.p1, self.p2
        else:
            p1, p2 = self.p2, self.p1
        if y < p1.y():
            return 10 + self._object_manager.point_dist(p, (p1.x(), p1.y()))
        elif y > p2.y():
            return 10 + self._object_manager.point_dist(p, (p2.x(), p2.y()))
        else:
            return 10 + (x - p1.x()) * (x - p1.x())

    def draw(self, cr):
        if self.selected():
            cr.set_source_rgb(0, 0, 1)
        elif self.active():
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 1, 0)
        cr.set_line_width(0.5)
        cr.set_dash([5, 5])
        cr.move_to(self.p1.x(), self.p1.y())
        cr.line_to(self.p2.x(), self.p2.y())
        cr.stroke()


class HorizDistance(TwoPointConstraint):
    def __init__(self, object_manager, objects):
        super(HorizDistance, self).__init__(object_manager, objects)
        if self.p1.x() > self.p2.x():
            self.p1, self.p2 = self.p2, self.p1

        dialog = gtk.Dialog("Enter distance")
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
            self.distance = float(entry1.get_text())
        else:
            del self
        dialog.destroy()

        self.label_distance = 100

    def constraints(self):
        return [
            ([(self.p2.point(), 1, 0), (self.p1.point(), -1, 0)], self.distance)
        ]

    def draw(self, cr):
        if self.selected():
            cr.set_source_rgb(0, 0, 1)
        elif self.active():
            cr.set_source_rgb(1, 0, 0)
        else:
            cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(0.3)
        cr.move_to(self.p1.x(), self.p1.y())
        cr.line_to(self.p1.x(), self.p1.y() + self.label_distance)
        cr.stroke()
        cr.move_to(self.p2.x(), self.p2.y())
        # Note: the p1 here is not a bug.
        cr.line_to(self.p2.x(), self.p1.y() + self.label_distance)
        cr.stroke()
        cr.move_to(self.p1.x(), self.p1.y() + self.label_distance)
        cr.show_text("%s" % (self.distance,))
        cr.stroke()

    def dist(self, p):
        return self._object_manager.point_dist(
            p,
            (self.p1.x(),
             self.p1.y() + self.label_distance)
        )

    def drag(self, offs_x, offs_y):
        self.label_distance += offs_y


class Array(Primitive):
    def __init__(self, object_manager, x, y, constructor,
                 nx=None, ny=None):
        super(Array, self).__init__(object_manager)

        if nx == None:
            dialog = gtk.Dialog("Enter dimensions")
            array = gtk.Table(2, 2)
            label1 = gtk.Label("# of pads (x): ")
            array.attach(label1, 0, 1, 0, 1)
            entry1 = gtk.Entry()
            array.attach(entry1, 1, 2, 0, 1)
            label1.show()
            entry1.show()
            label2 = gtk.Label("# of pads (y): ")
            array.attach(label2, 0, 1, 1, 2)
            entry2 = gtk.Entry()
            array.attach(entry2, 1, 2, 1, 2)
            label2.show()
            entry2.show()
            array.show()
            dialog.get_content_area().add(array)
            # widget.connect("clicked", lambda x: win2.destroy())
            dialog.add_button("Ok", 1)
            dialog.add_button("Cancel", 2)
            result = dialog.run()
            if result == 1:
                self.x = int(entry1.get_text())
                self.y = int(entry2.get_text())
            else:
                del self
            dialog.destroy()
        else:
            self.x = nx
            self.y = ny

        self.elements = []
        for i in range(self.x):
            for j in range(self.y):
                p = constructor(object_manager,
                                x + (i - self.x/2) * 30,
                                y + (j - self.y/2) * 30)

                self.elements.append(p)
                object_manager.add_primitive(p, constraining=False,
                                             check_overconstraints=False)

    def dependencies(self):
        return self.elements

    def children(self):
        return self.elements

    def draw(self, cr):
        for child in self.children():
            child.draw(cr)

    def p(self, i, j):
        return self.elements[j + self.y * i]

    def constraints(self):
        all_constraints = []
        for child in self.children():
            all_constraints.extend(child.constraints())

        # Horizontal/vertical
        for i in range(0, min(self.x, 2)):
            for j in range(0, self.y - 1):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 1, 0),
                         (self.p(i, j + 1).center_point(), -1, 0),
                         ], 0),
                )

        for i in range(0, self.x - 1):
            for j in range(0, min(self.y, 2)):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 0, 1),
                         (self.p(i + 1, j).center_point(), 0, -1),
                         ], 0),
                )

        # Same distance
        for i in range(0, self.x):
            for j in range(0, self.y - 2):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 0, 1),
                         (self.p(i, j + 1).center_point(), 0, -2),
                         (self.p(i, j + 2).center_point(), 0, 1),
                         ], 0),
                )

        for i in range(0, self.x - 2):
            for j in range(0, self.y):
                all_constraints.append(
                    (
                        [(self.p(i, j).center_point(), 1, 0),
                         (self.p(i + 1, j).center_point(), -2, 0),
                         (self.p(i + 2, j).center_point(), 1, 0),
                         ], 0),
                )

        # Same size
        p0_dimensions = self.p(0, 0).dimensions_to_constrain()
        for i in range(0, self.x):
            for j in range(0, self.y):
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
