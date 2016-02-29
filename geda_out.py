from primitives import Pad, Ball

class GedaOut(object):
    @staticmethod
    def write_ball(ball):
        print """Pad [ {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm "{}" "{}" "" ]""".format(
            ball.x, ball.y, ball.x, ball.y,
            ball.r*2, ball.r*2, ball.r*2, 0, 0)

    @staticmethod
    def write_pad(pad):
        if pad.w > pad.h:
            x0 = pad.x0 + pad.h/2.
            x1 = pad.x1 - pad.h/2.
            y = (pad.y0 + pad.y1)/2.
            print """Pad [{:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm 1200 {:.6f}mm "" "{}" 0x4101]""".format(
                x0, y, x1, y, pad.h, pad.h + 1, pad.number() if pad.number() is not None else 0)
        else:
            y0 = pad.y0 + pad.w/2.
            y1 = pad.y1 - pad.w/2.
            x = (pad.x0 + pad.x1)/2.
            print """Pad [{:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm 1200 {:.6f}mm "" "{}" 0x4101]""".format(
                x, y0, x, y1, pad.w, pad.w + 1, pad.number() if pad.number() is not None else 0)


    @staticmethod
    def write(primitive_list):
        print """Element [0x00 "bga_15" "" "" 0.000000mm 0.000000mm 0.000000mm 0.000000mm 0 100 0x00]"""
        print "("
        functab = [
            (Ball, GedaOut.write_ball),
            (Pad, GedaOut.write_pad),
        ]
        for primitive in primitive_list:
            for ty, func in functab:
                if isinstance(primitive, ty):
                    func(primitive)
        print ")"
