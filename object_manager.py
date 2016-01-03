# This file keeps track of what objects we have, and is responsible for
# calculating positions and enforcing constraints on those objects.
# Eventually, the core solver should be moved to a new file.
# Actually, the solver should be entirely rewritten.

from collections import defaultdict
from math import sqrt
from numpy import array, dot, vdot, matrix
from numpy.linalg import matrix_rank, solve, inv

class ObjectManager(object):
    def __init__(self):
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
        self._cached_target = None
        self._cached_point_to_matrix = None
        self._target_map_x = {}
        self._target_map_y = {}
        # All primitives we have.
        self.primitives = []
        # All primitives that should be drawn on the screen.
        self.draw_primitives = []

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

    def add_primitive(self, primitive, draw=True):
        self.primitives.append(primitive)
        if draw:
            self.draw_primitives.append(primitive)

    def point_dist(self, p1, p2):
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return (dx*dx + dy*dy)

    def alloc_point(self, x, y):
        old = self._next_point_idx
        self._next_point_idx += 1
        self._all_points.add(old)
        self._point_lru.append(old)
        self._cached_matrix = None
        self._cached_target = None
        self._point_coords[old] = (x, y)

        return old

    def free_point(self, point_idx):
        self._all_points.remove(self.point_idx)

    def _lru_update(self, p):
        for i in range(len(self._point_lru)):
            if self._point_lru[i] == p:
                self._point_lru = ([p] + self._point_lru[0:i]
                                      + self._point_lru[i+1:])
                break

    def set_point_coords(self, point, x, y):
        self._lru_update(point)
        self._point_coords[point] = (x, y)
        self._update_point(point, x, y)

    def point_x(self, point):
        return self._point_coords[point][0]

    def point_y(self, point):
        return self._point_coords[point][1]

    def point_coords(self, point):
        return (self.point_x(point), self.point_y(point))

    # TODO: most stuff below here is absolutely terrible and inefficient
    # and should be rewritten.

    def add_ortho_row(self, ortho_m, new_row):
        cur_row = matrix(new_row)

        for other_row in ortho_m:
            dot_prod = vdot(new_row, other_row)
            cur_row = cur_row - dot_prod * matrix(other_row)
        magnitude = sqrt(vdot(cur_row.tolist(), cur_row.tolist()))
        cur_row = cur_row / magnitude
        ortho_m.append(cur_row.tolist()[0])

    def build_ortho(self, m):
        m = matrix(m)
        new_matrix = []
        for row in m:
            self.add_ortho_row(new_matrix, row)
        return new_matrix

    def can_add(self, ortho_m, idx):
        r = ortho_m[0]
        new_row = sum(om[idx] * matrix(om) for om in ortho_m)
        for i, j in enumerate(new_row.tolist()[0]):
            if i == idx and round(j, 5) != 1:
                return True
            if i != idx and round(j, 5) != 0:
                return True
        return False

    def build_matrix(self, constraints, point_to_matrix):
        n = len(self._all_points)
        targets = []
        matrix = []

        for (coeffs, target) in constraints:
            row = [0] * 2 * n
            for (pt, coeffx, coeffy) in coeffs:
                row[2 * point_to_matrix[pt]] = coeffx
                row[2 * point_to_matrix[pt] + 1] = coeffy
            matrix.append(row)
            targets.append(target)

        ortho_matrix = self.build_ortho(matrix)

        self._target_map_x = {}
        self._target_map_y = {}
        for pt in self._point_lru:
            coords = self._point_coords[pt]
            row1 = [0] * 2 * n
            row2 = [0] * 2 * n
            row1[2 * point_to_matrix[pt]] = 1
            row2[2 * point_to_matrix[pt] + 1] = 1

            if self.can_add(ortho_matrix, 2 * point_to_matrix[pt]):
                self._target_map_x[pt] = len(targets)
                targets.append(coords[0])
                matrix.append(row1)
                self.add_ortho_row(ortho_matrix, row1)

            if self.can_add(ortho_matrix, 2 * point_to_matrix[pt] + 1):
                self._target_map_y[pt] = len(targets)
                targets.append(coords[1])
                matrix.append(row2)
                self.add_ortho_row(ortho_matrix, row2)

            if len(matrix) == 2 * n:
                break

        # TODO: optimize this
        return (array(matrix), array(targets))

    def update_points(self):
        constraints = []
        for p in self.primitives:
            constraints = constraints + p.constraints()

        point_to_matrix = {}
        idx = 0
        for point in self._all_points:
            point_to_matrix[point] = idx
            idx += 1
        assert idx == len(self._all_points)
        m, t = self.build_matrix(constraints, point_to_matrix)
        self._cached_matrix = inv(m)
        self._cached_target = t
        self._cached_point_to_matrix = point_to_matrix
        sol = dot(self._cached_matrix, t)
        sol = zip(sol[::2], sol[1::2])
        for point, mat_point in point_to_matrix.iteritems():
            self._point_coords[point] = sol[mat_point]

    def _update_point(self, p, x, y):
        if p in self._target_map_x:
            self._cached_target[self._target_map_x[p]] = x
        if p in self._target_map_y:
            self._cached_target[self._target_map_y[p]] = y

        sol = dot(self._cached_matrix, self._cached_target)
        sol = zip(sol[::2], sol[1::2])
        for point, mat_point in self._cached_point_to_matrix.iteritems():
            self._point_coords[point] = sol[mat_point]

