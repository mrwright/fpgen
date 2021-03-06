# This file keeps track of what objects we have, and is responsible for
# calculating positions and enforcing constraints on those objects.
# Eventually, the core solver should be moved to a new file.
# Actually, the solver should be entirely rewritten.

from collections import defaultdict
from copy import deepcopy

from exceptiontypes import OverconstrainedException
from primitives import PRIMITIVE_TYPES, Point
from units import UnitNumber

class ObjectManager(object):
    def __init__(self, fp_name, default_clearance, default_mask):
        self.fp_name = fp_name
        self.default_clearance = default_clearance
        self.default_mask = default_mask

        # Points are each assigned a number; next_point_idx contains the number
        # to assign to the next point we allocate.
        self._next_point_idx = 0
        # The set of indices of points that are active.
        # This won't necessarily be the interval [0, next_point_idx) because
        # points may be removed.
        self._all_points = set()
        # The current coordinates of each point. Maps point indices to
        # (x, y) tuples.
        self._point_coords = {}
        # LRU of point indices. This is used to be a bit smarter when we're
        # dragging points: we'll try harder to keep more recently moved
        # points where they are.
        self._point_lru = []
        # Caches of various internal things I should really document
        # at some point.
        self._cached_matrix = None
        # All primitives we have. TODO: make these sets
        self.primitives = []
        # All primitives that should be drawn on the screen.
        self.draw_primitives = []
        # All primitives whose constraints we should consider.
        self.constraining_primitives = []
        # All suppressed primitives
        self.suppressed_primitives = set()
        # Map from each primitive to its parent.
        self.parent_map = {}
        self.degrees_of_freedom = 0
        # Global storage for each class.
        self.clsdata = {}

    def to_dict(self):
        # Note: a lot of stuff here could be made more efficient, but there's
        # not really any point.
        primitive_dicts = [dict(
            index=idx,
            primitive_type=primitive.TYPE(),
            primitive_dict=primitive.to_dict()
        ) for idx, primitive in enumerate(self.primitives)]
        return dict(
            fp_name=self.fp_name,
            default_mask=self.default_mask.to_dict(),
            default_clearance=self.default_clearance.to_dict(),
            next_point_idx=self._next_point_idx,
            all_points=list(self._all_points),
            point_coords=deepcopy(self._point_coords),
            primitives=primitive_dicts,
            draw_primitives=[self.primitive_idx(primitive)
                             for primitive in self.draw_primitives],
            constraining_primitives=[self.primitive_idx(primitive)
                                     for primitive
                                       in self.constraining_primitives],
            suppressed_primitives=[self.primitive_idx(primitive)
                                   for primitive
                                   in self.suppressed_primitives],
        )

    @staticmethod
    def from_dict(dictionary):
        object_manager = ObjectManager(
            dictionary['fp_name'],
            UnitNumber.from_dict(dictionary['default_clearance']),
            UnitNumber.from_dict(dictionary['default_mask']),
        )
        object_manager._all_points = set(dictionary['all_points'])
        object_manager._point_lru = dictionary['all_points']
        object_manager._next_point_idx = dictionary['next_point_idx']
        object_manager._point_coords = {
            int(point): tuple(pc)
            for point, pc in dictionary['point_coords'].iteritems()
        }

        # Create the actual primitives. This requires a topological sort, which
        # can be done more efficiently than this but there's no good reason to.
        primitive_dicts = dictionary['primitives']
        object_manager.primitives = [None] * len(primitive_dicts)
        while not all(primitive for primitive in object_manager.primitives):
            for primitive_dict in primitive_dicts:
                if not all(object_manager.primitives[i]
                           for i in primitive_dict.get('deps', [])):
                    continue
                # At this point, we have a primitive that's ready to be created.
                primitive_cls = PRIMITIVE_TYPES[
                    primitive_dict['primitive_type']
                ]
                primitive = primitive_cls.from_dict(
                    object_manager,
                    primitive_dict['primitive_dict']
                )
                object_manager.primitives[primitive_dict['index']] = primitive
        object_manager.draw_primitives = [
            object_manager.primitives[idx]
            for idx in dictionary['draw_primitives']
        ]
        object_manager.constraining_primitives = [
            object_manager.primitives[idx]
            for idx in dictionary['constraining_primitives']
        ]
        object_manager.suppressed_primitives = set(
            object_manager.primitives[idx]
            for idx in dictionary['suppressed_primitives']
        )
        object_manager.update_points()
        object_manager.update_parent_map()

        return object_manager

    def primitive_idx(self, primitive):
        for i, this_primitive in enumerate(self.primitives):
            if primitive == this_primitive:
                return i
        return None

    def update_parent_map(self):
        self.parent_map.clear()
        for primitive in self.primitives:
            for child in primitive.children():
                self.parent_map[child] = primitive

    def closest(self, x, y):
        '''
        Determine the primitive "closest" to the given coordinates.
        '''
        dist = None
        p = None
        for primitive in self.primitives:
            this_dist = primitive.dist((x, y))
            if this_dist is not None and (p is None or this_dist < dist):
                dist = this_dist
                p = primitive
        return (p, dist)

    def all_within(self, x, y, radius):
        l = []
        for primitive in self.primitives:
            this_dist = primitive.dist((x, y))
            if this_dist is not None and this_dist < radius:
                l.append((this_dist, primitive))

        l.sort(key=lambda x: x[0])
        return l

    def add_primitive(self, primitive, draw=True, constraining=True,
                      check_overconstraints=True):
        self.primitives.append(primitive)
        if draw:
            self.draw_primitives.append(primitive)
        if constraining:
            self.constraining_primitives.append(primitive)
        if check_overconstraints:
            try:
                self.update_points()
            except OverconstrainedException:
                print "OVERCONSTRAINED"
                self.primitives.pop()
                if draw:
                    self.draw_primitives.pop()
                if constraining:
                    self.constraining_primitives.pop()
                raise
        # Note: we don't need to recompute the entire primitive map here, but it
        # shouldn't be a bottleneck.
        self.update_parent_map()

    def delete_primitive(self, obj):
        to_remove = set([obj])
        while True:
            changed = False
            l = len(to_remove)
            new_to_remove = set()
            for c in to_remove:
                new_to_remove.update(c.children())
                if not new_to_remove.issubset(to_remove):
                    changed = True
            to_remove.update(new_to_remove)
            changed = changed or l != len(to_remove)
            for p in self.primitives:
                if p in to_remove:
                    continue
                if to_remove.intersection(p.dependencies() + p.children()):
                    to_remove.update([p])
                    changed = True
            if not changed:
                break
        if any(not x.can_delete() for x in to_remove):
            return
        for p in to_remove:
            self.remove_primitive(p)
            p.delete()

        self.update_points()

    def remove_primitive(self, obj):
        '''
        Remove the primitive directly, without removing dependencies
        or calling the delete method.
        '''
        self.primitives.remove(obj)
        # TODO: these should be sets.
        if obj in self.draw_primitives:
            self.draw_primitives.remove(obj)
        if obj in self.constraining_primitives:
            self.constraining_primitives.remove(obj)

    def alloc_point(self, x, y):
        old = self._next_point_idx
        self._next_point_idx += 1
        self._all_points.add(old)
        self._point_lru.append(old)
        self._cached_matrix = None
        self._point_coords[old] = (x, y)

        return old

    def free_point(self, point_idx):
        self._all_points.remove(point_idx)
        self._point_lru.remove(point_idx)
        del self._point_coords[point_idx]
        self._cached_matrix = None

    def _lru_update(self, p):
        for i in range(len(self._point_lru)):
            if self._point_lru[i] == p:
                self._point_lru = ([p] + self._point_lru[0:i]
                                   + self._point_lru[i+1:])
                break

    def set_point_coords(self, point, x, y):
        self._lru_update(point)
        self._point_coords[point] = (x, y)

    def point_x(self, point):
        return self._point_coords[point][0]

    def point_y(self, point):
        return self._point_coords[point][1]

    def point_coords(self, point):
        return (self.point_x(point), self.point_y(point))

    def toggle_suppressed(self, primitive):
        if primitive in self.suppressed_primitives:
            self.suppressed_primitives.remove(primitive)
        else:
            self.suppressed_primitives.add(primitive)

    def is_suppressed(self, primitive):
        return primitive in self.suppressed_primitives

    @classmethod
    def eliminate(cls, current, new, mins, inv, target_pt, target_val):
        '''
        Gaussian elimination.

        current: list of maps from column indices to coefficients.
        new: a constraint to be added.
        mins: dictionary of index->row index.
        inv: same as current; will end up with the inverse of the matrix.
        '''
        remaining = list(new)
        new_inv = defaultdict(int)
        new_inv[target_pt] = target_val
        while remaining:
            # TODO: this could be done a lot better.
            x = remaining.pop()
            if x in mins:
                i = mins[x]
                factor = new[x]
                for y, v in current[i].iteritems():
                    new[y] -= v * factor
                    if new[y]:
                        remaining.append(y)
                for y, v in inv[i].iteritems():
                    if y not in new_inv:
                        new_inv[y] = 0
                    new_inv[y] -= v * factor

        for x in list(new):
            if round(new[x], 4) == 0:
                del new[x]

        try:
            j = min(new)
            assert j not in mins, new
        except ValueError:
            # Row is all zeros.
            return False

        v = new[j]
        for x in new:
            new[x] /= float(v)
        for x in new_inv:
            new_inv[x] /= float(v)

        for x in list(new_inv):
            if new_inv[x] == 0:
                del new_inv[x]

        assert new[j] == 1

        count = 0
        for idx, row in enumerate(current):
            if j in row:
                count += 1
                inv_row = inv[idx]
                factor = row[j]
                for y, v in new.iteritems():
                    if y not in row:
                        row[y] = 0
                    row[y] -= v * factor
                for y, v in new_inv.iteritems():
                    inv_row[y] -= v * factor
                assert row[j] == 0
                for i in list(row):
                    if round(row[i], 4) == 0:
                        del row[i]
                for i in list(inv_row):
                    if inv_row[i] == 0:
                        del inv_row[i]

        mins[j] = len(current)
        current.append(new)
        inv.append(new_inv)

        return True

    def build_matrix(self, constraints, secondary_constraints, points,
                     dragging_point):
        def constrain_point(pt, current_dictmat, current_mins, inv):
            row1dict = defaultdict(int)
            row2dict = defaultdict(int)
            row1dict[2 * pt] = 1
            row2dict[2 * pt + 1] = 1

            self.eliminate(current_dictmat, row1dict, current_mins, inv,
                           2 * pt, 1)
            self.eliminate(current_dictmat, row2dict, current_mins, inv,
                           2 * pt + 1, 1)

        def constraint_to_row(coeffs, target):
            rowdict = defaultdict(int)
            for (pt, coeffx, coeffy) in coeffs:
                rowdict[2 * pt] += coeffx
                rowdict[2 * pt + 1] += coeffy
            return rowdict

        n = len(self._all_points)
        targets = []
        inv = []

        current_dictmat = []
        current_mins = {}

        for (coeffs, target) in constraints:
            rowdict = constraint_to_row(coeffs, target)
            result = self.eliminate(current_dictmat, rowdict, current_mins, inv,
                                    None, target)
            if not result:
                return False
        # We now have a matrix with all explicit constraints.
        print "Degrees of freedom: %d" % (2 * n - len(current_dictmat))
        self.degrees_of_freedom = (2 * n - len(current_dictmat))

        if dragging_point is not None:
            constrain_point(dragging_point, current_dictmat, current_mins, inv)

        for (coeffs, target) in secondary_constraints:
            rowdict = constraint_to_row(coeffs, target)
            self.eliminate(current_dictmat, rowdict, current_mins, inv,
                           None, target)

        for pt in points + self._point_lru:
            constrain_point(pt, current_dictmat, current_mins, inv)

            if len(current_dictmat) == 2 * n:
                break

        new_inv = {}
        for pt_idx, row_idx in current_mins.iteritems():
            new_inv[pt_idx] = inv[row_idx]

        return new_inv

    def _coord(self, pt_ind):
        return self.point_coords(pt_ind/2)[pt_ind%2]

    def _pt_val(self, pt_ind):
        pt_row = self._cached_matrix[pt_ind]
        pt_val = sum(self._coord(target_ind) * float(target_coeff)
                     for target_ind, target_coeff in pt_row.iteritems()
                     if target_ind is not None)
        pt_val += pt_row[None]
        return float(pt_val)

    def update_all_point_coords(self):
        for point in self._all_points:
            self._point_coords[point] = (self._pt_val(point * 2),
                                         self._pt_val(point * 2 + 1))

    def update_points(self, dragging_object=None):
        constraints = []
        secondary_constraints = []
        if dragging_object:
            (drag_constraints,
             points) = dragging_object.drag_constraints(None)
            secondary_constraints.extend(drag_constraints)
        else:
            points = []
            for p in self.constraining_primitives:
                secondary_constraints.extend(p.secondary_constraints())

        for p in self.constraining_primitives:
            constraints.extend(p.constraints())

        if isinstance(dragging_object, Point):
            dragging_point = dragging_object.point()
        else:
            dragging_point = None

        m = self.build_matrix(constraints, secondary_constraints, points,
                              dragging_point)
        if not m:
            raise OverconstrainedException
        self._cached_matrix = m
        self.update_all_point_coords()
        return True
