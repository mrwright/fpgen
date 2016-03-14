def _constrain_horiz_or_vert(points, horizontalness, verticalness):
    constraints = []
    p0 = points[0]
    for p in points[1:]:
        constraints.append(
            ([(p0.point(), verticalness, horizontalness),
              (p.point(), -verticalness, -horizontalness)], 0)
        )
    return constraints

def constrain_horiz(points):
    return _constrain_horiz_or_vert(points, 1, 0)

def constrain_vert(points):
    return _constrain_horiz_or_vert(points, 0, 1)

def _equal_space(points, horizontalness, verticalness):
    def p(i, j):
        return points[i + j].point()
    constraints = []
    for i in range(0, len(points) - 2):
        constraints.append(
            ([(p(i, 0), horizontalness, verticalness),
              (p(i, 1), -2*horizontalness, -2*verticalness),
              (p(i, 2), horizontalness, verticalness)], 0)
        )
    return constraints

def equal_space_horiz(points):
    return _equal_space(points, 1, 0)

def equal_space_vert(points):
    return _equal_space(points, 0, 1)

def constrain_ball(points):
    '''
    Given a list of five points (top, left, center, right, bottom), return
    a list of constraints appropriate for a ball.
    '''
    def p(x):
        return points[x].point()

    # Points in a row should be aligned horizontally; points in a column
    # vertically.
    horiz_constraints = constrain_horiz(points[1:4])
    vert_constraints = constrain_vert(points[:5:2])

    # Spacing should be equal, in the horizontal and vertical directions.
    eq_horiz_constraints = equal_space_horiz(points[1:4])
    eq_vert_constraints = equal_space_vert(points[:5:2])
    # Finally, the radius is the same in any direction.
    eq_constraints = [
        ([(p(2), -1, 1),
          (p(3), 1, 0),
          (p(4), 0, -1),
        ], 0)
    ]
    return (horiz_constraints +
            vert_constraints +
            eq_horiz_constraints +
            eq_vert_constraints +
            eq_constraints)

