# Table of units, and the conversion factor with internal units.
UNITS = {
    "iu" : 1, # Internal units are mils.
    "in" : 1000,
    "inch" : 1000,
    "inches" : 1000,
    "mil" : 1,
    "mils" : 1,
    "mm" : 39.370078740157,
    "cm" : 393.70078740157,
}

class UnitNumber(object):
    def __init__(self, value, unit):
        assert unit in UNITS
        self._value = value
        self._unit = unit

    @property
    def value(self):
        return self._value

    @property
    def unit(self):
        return self._unit

    @classmethod
    def from_str(cls, s, default_unit=None):
        splitstr = s.split()
        if len(splitstr) > 2:
            return ValueError()
        elif len(splitstr) == 2:
            val = float(splitstr[0])
            unit = splitstr[1]
            if not unit in UNITS:
                raise ValueError()
            return cls(val, unit)
        else:
            if default_unit:
                assert default_unit in UNITS
                try:
                    num = float(s)
                except ValueError:
                    pass
                else:
                    return cls(num, default_unit)
            for i in xrange(len(s) - 1, -1, -1):
                num, unit = s[:i], s[i:]
                if unit not in UNITS:
                    continue
                try:
                    num = float(num)
                except ValueError:
                    continue

                return cls(num, unit)
        raise ValueError()

    def __str__(self):
        return "{} {}".format(self._value, self._unit)

    def to(self, unit):
        assert unit in UNITS
        return self._value * UNITS[self._unit] / UNITS[unit]

    def to_dict(self):
        return dict(
            value=self._value,
            unit=self._unit,
        )

    @classmethod
    def from_dict(cls, dictionary):
        return cls(dictionary['value'], dictionary['unit'])
