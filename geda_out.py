from primitives import (
    Ball,
    Pad,
    Pin,
)

class GedaOut(object):
    @staticmethod
    def write_ball(ball):
        mask = float(ball.mask().to("mil")) * 2
        clearance = float(ball.clearance().to("mil")) * 2

        print """Pad [ {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil "{}" "{}" "" ]""".format(
            ball.x, ball.y, ball.x, ball.y,
            ball.r*2, # Thickness
            clearance, # Clearance
            ball.r*2 + mask, # Mask
            0, 0)

    @staticmethod
    def write_pad(pad):
        mask = float(pad.mask().to("mil")) * 2
        clearance = float(pad.clearance().to("mil")) * 2
        if pad.w > pad.h:
            x0 = pad.x0 + pad.h/2.
            x1 = pad.x1 - pad.h/2.
            y = (pad.y0 + pad.y1)/2.
            print """Pad [{:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil "" "{}" 0x101]""".format(
                x0, y, x1, y,
                pad.h, # Thickness
                clearance, # Clearance
                pad.h + mask, # Mask
                pad.number() if pad.number() is not None else '')
        else:
            y0 = pad.y0 + pad.w/2.
            y1 = pad.y1 - pad.w/2.
            x = (pad.x0 + pad.x1)/2.
            print """Pad [{:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil "" "{}" 0x4101]""".format(
                x, y0, x, y1,
                pad.w, # Thickness
                clearance, # Clearance
                pad.w + mask, # Mask
                pad.number() if pad.number() is not None else '')

    @staticmethod
    def write_pin(pin):
        mask = pin.mask().to("mil") * 2
        clearance = pin.clearance().to("mil") * 2
        print """Pin [{:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil {:.6f}mil "" "{}" "via"]""".format(
            pin.x, pin.y,
            pin.ring_r * 2,
            clearance,
            mask,
            pin.hole_r * 2,
            pin.number() if pin.number() is not None else ''
        )


    @staticmethod
    def write(object_manager):
        fp_name = object_manager.fp_name
        primitive_list = object_manager.primitives
        print """Element [0x00 "{}" "{}" "{}" 0.000000mil 0.000000mil 0.000000mil 0.000000mil 0 100 0x00]""".format(fp_name, fp_name, fp_name)
        print "("
        functab = [
            (Ball, GedaOut.write_ball),
            (Pad, GedaOut.write_pad),
            (Pin, GedaOut.write_pin),
        ]
        for primitive in primitive_list:
            for ty, func in functab:
                if isinstance(primitive, ty):
                    func(primitive)
        print ")"
