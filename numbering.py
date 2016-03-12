# This file contains various pin/pad/ball numbering schemes we might want to
# use.

from ui_utils import (
    BoolEntry,
    NumberEntry,
)

class _NUMBER_CONST_WIDTH(object):
    pass

class _NUMBER_CONST_HEIGHT(object):
    pass

NUMBER_CONST_HEIGHT = _NUMBER_CONST_HEIGHT()
NUMBER_CONST_WIDTH = _NUMBER_CONST_WIDTH()

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

    @classmethod
    def TYPE(cls):
        for type_id, (ty, name) in enumerate(ALL_NUMBERINGS):
            if ty == cls:
                return type_id
        raise ValueError()

    def to_dict(self):
        raise NotImplementedError()

    @classmethod
    def from_dict(cls, dictionary):
        raise NotImplementedError()

    # TODO: "defaults" method for objects that already exist, for editing the settings.

class NoNumbers(Numbering):
    def __init__(self):
        pass

    def number_of(self, i, j):
        return None

    @classmethod
    def applies(cls, w, h):
        return True

    @classmethod
    def fields(cls):
        return []

    @classmethod
    def new(cls, w, h, fields):
        return cls()

    def to_dict(self):
        return dict()

    @classmethod
    def from_dict(cls, dictionary):
        return cls.new()

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
            ("Starting index", NumberEntry(int), 1),
            ("Increment", NumberEntry(int), 1),
            ("Reversed", BoolEntry(), False),
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

    def to_dict(self):
        return dict(
            start=self._start,
            skip=self._skip,
        )

    @classmethod
    def from_dict(cls, dictionary):
        return cls(dictionary['start'], dictionary['skip'])

class OneDLetterRange(OneDNumberRange):
    # TODO: this class is a huge hack right now and doesn't at all work right.

    def number_of(self, i, j):
        idx = super(OneDLetterRange, self).number_of(i, j)
        return chr(ord('A') + idx)

    @classmethod
    def fields(cls):
        return [
            ("Starting index", NumberEntry(int), 1),
            ("Increment", NumberEntry(int), 1),
            ("Reversed", BoolEntry(), False),
        ]

class TwoDNumbers(Numbering):
    def __init__(self, start, x_skip, y_skip, x_zigzag, y_zigzag, width, height):
        self._start = start
        self._x_skip = x_skip
        self._y_skip = y_skip
        self._x_zigzag = x_zigzag
        self._y_zigzag = y_zigzag
        self._width = width
        self._height = height

    def number_of(self, i, j):
        if self._x_zigzag and (j % 2) > 0:
            i = self._width - 1 - i

        if self._y_zigzag and (i % 2) > 0:
            j = self._height - 1 - j

        return str(self._start + self._x_skip * i + self._y_skip * j)

    @classmethod
    def applies(cls, w, h):
        return w > 0 and h > 0

    @classmethod
    def fields(cls):
        return [
            ("Starting index", NumberEntry(int), 1),
            ("Increment (x)", NumberEntry(int), 1),
            ("Increment (y)", NumberEntry(int), NUMBER_CONST_WIDTH),
            ("Reversed (x)", BoolEntry(), False),
            ("Reversed (y)", BoolEntry(), False),
            ("Zigzag (x)", BoolEntry(), False),
            ("Zigzag (y)", BoolEntry(), False),
        ]

    @classmethod
    def new(cls, w, h, fields):
        assert cls.applies(w, h)
        max_dim = max(w, h)
        start_idx = fields[0]
        x_increment = fields[1]
        y_increment = fields[2]
        x_reversed = fields[3]
        y_reversed = fields[4]
        x_zigzag = fields[5]
        y_zigzag = fields[6]

        if x_reversed:
            start_idx = start_idx + (w - 1) * x_increment
            x_increment = -x_increment
        if y_reversed:
            start_idx = start_idx + (h - 1) * y_increment
            y_increment = -y_increment

        return cls(start_idx, x_increment, y_increment, x_zigzag, y_zigzag, w, h)

    def to_dict(self):
        return dict(
            start=self._start,
            x_skip=self._x_skip,
            y_skip=self._y_skip,
            x_zigzag=self._x_zigzag,
            y_zigzag=self._y_zigzag,
            width=self._width,
            height=self._height,
        )

    @classmethod
    def from_dict(cls, dictionary):
        return cls(
            dictionary['start'],
            dictionary['x_skip'],
            dictionary['y_skip'],
            dictionary['x_zigzag'],
            dictionary['y_zigzag'],
            dictionary['width'],
            dictionary['height'],
        )

ALL_NUMBERINGS = [
    (NoNumbers, "Do not assign numbers"),
    (OneDNumberRange, "Number range with increment"),
    (OneDLetterRange, "Letter range with increment"),
    (TwoDNumbers, "Number increments in two dimensions"),
]
