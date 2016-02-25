# This file contains various pin/pad/ball numbering schemes we might want to use.

class Numbering(object):
    def numer_of(self, i, j):
        return NotImplementedError()

    @classmethod
    def applies(cls, w, h):
        return NotImplementedError()

    @classmethod
    def fields(cls):
        return NotImplementedError()

    @classmethod
    def new(cls, w, h, fields):
        return NotImplementedError()

class OneDNumberRange(Numbering):
    def __init__(self, start, skip):
        self._start = start
        self._skip = skip

    def number_of(self, i, j):
        assert i == 0 or j == 0
        idx = max(i, j)
        return str(self._start + self._skip * idx)

    @classmethod
    def applies(cls, w, h):
        return w == 1 or h == 1

    @classmethod
    def fields(cls):
        return [
            ("Starting index", int, None),
            ("Increment", int, 1),
            ("Reversed", bool, False),
        ]

    @classmethod
    def new(cls, w, h, fields):
        assert cls.applies(w, h)
        max_dim = max(w, h)
        start_idx = fields[0]
        increment = fields[1]
        is_reversed = fields[2]

        if is_reversed:
            start_idx = start_idx + (max_dim - 1) * increment
            increment = -increment

        return cls(start_idx, increment)

class OneDLetterRange(OneDNumberRange):
    # TODO: this class is a huge hack right now and doesn't at all work right.

    def number_of(self, i, j):
        idx = super(OneDLetterRange, self).number_of(i, j)
        return chr(ord('A') + idx)

    @classmethod
    def fields(cls):
        return [
            ("Starting letter index", int, None),
            ("Increment", int, 1),
            ("Reversed", bool, False),
        ]


all_numberings = [
    (OneDNumberRange, "Number range with increment"),
    (OneDLetterRange, "Letter range with increment"),
]
