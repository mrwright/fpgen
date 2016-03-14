import math

def point_dist(p1, p2):
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return (dx*dx + dy*dy)

def line_dist(x1, y1, x2, y2, x, y):
    def normalize(p):
        mag = p[0] * p[0] + p[1] * p[1]
        sqrtmag = math.sqrt(mag)
        return (p[0]/sqrtmag, p[1]/sqrtmag), sqrtmag
    v1, _ = normalize((x - x1, y - y1))
    v2, _ = normalize((x - x2, y - y2))
    v3_orig = (x2 - x1, y2 - y1)
    if v3_orig[0] == 0 and v3_orig[1] == 0:
        return point_dist((x1, y1), (x, y))

    v3, v3mag = normalize(v3_orig)

    if v1[0] * v3[0] + v1[1] * v3[1] < 0:
        res = point_dist((x, y), (x1, y1))
    elif v2[0] * v3[0] + v2[1] * v3[1] > 0:
        res = point_dist((x, y), (x2, y2))
    else:
        res = abs(
            v3_orig[1] * x - v3_orig[0] * y
            + x2 * y1 - y2 * x1
        ) / v3mag
        res = res * res

    return res
