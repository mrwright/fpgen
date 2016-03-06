from primitives import Pad, Ball

class GedaOut(object):
    @staticmethod
    def write_ball(ball):
        mask = float(ball.mask()) * 2
        clearance = float(ball.clearance()) * 2

        print """Pad [ {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm "{}" "{}" "" ]""".format(
            ball.x, ball.y, ball.x, ball.y,
            ball.r*2, # Thickness
            clearance, # Clearance
            ball.r*2 + mask, # Mask
            0, 0)

    @staticmethod
    def write_pad(pad):
        mask = float(pad.mask()) * 2
        clearance = float(pad.clearance()) * 2
        if pad.w > pad.h:
            x0 = pad.x0 + pad.h/2.
            x1 = pad.x1 - pad.h/2.
            y = (pad.y0 + pad.y1)/2.
            print """Pad [{:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm "" "{}" 0x4101]""".format(
                x0, y, x1, y,
                pad.h, # Thickness
                clearance, # Clearance
                pad.h + mask, # Mask
                pad.number() if pad.number() is not None else 0)
        else:
            y0 = pad.y0 + pad.w/2.
            y1 = pad.y1 - pad.w/2.
            x = (pad.x0 + pad.x1)/2.
            print """Pad [{:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm {:.6f}mm "" "{}" 0x4101]""".format(
                x, y0, x, y1,
                pad.w, # Thickness
                clearance, # Clearance
                pad.w + mask, # Mask
                pad.number() if pad.number() is not None else 0)


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
