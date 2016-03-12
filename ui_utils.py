import pygtk
pygtk.require('2.0')
import gtk

from units import UnitNumber, UNITS

ERROR_COLOR = gtk.gdk.Color(65535, 0, 0)

class ValidatingInput(object):
    def mark_invalid(self):
        self.modify_base(gtk.STATE_NORMAL, ERROR_COLOR)

    def mark_valid(self):
        self.modify_base(gtk.STATE_NORMAL, None)

    def valid(self):
        raise NotImplementedError()

    def set_val(self, val):
        raise NotImplementedError()

    def validate(self):
        raise NotImplementedError()

class ValidatingEntry(gtk.Entry, ValidatingInput):
    def __init__(self):
        super(ValidatingEntry, self).__init__()
        self.connect("focus_out_event",
                     lambda _, __ : self.validate())
        self.connect("focus_in_event",
                     lambda _, __ : self.mark_valid())

    def mark_invalid(self):
        self.modify_base(gtk.STATE_NORMAL, ERROR_COLOR)

    def mark_valid(self):
        self.modify_base(gtk.STATE_NORMAL, None)

    def valid(self):
        raise NotImplementedError()

    def set_val(self, val):
        raise NotImplementedError()

    def validate(self):
        if self.valid():
            self.mark_valid()
        else:
            self.mark_invalid()

class NumberEntry(ValidatingEntry):
    def __init__(self, number_cls, allow_neg=True, allow_zero=True,
                 allow_empty=False, max_val=None):
        super(NumberEntry, self).__init__()
        self._number_cls = number_cls
        self._allow_neg = allow_neg
        self._allow_zero = allow_zero
        self._allow_empty = allow_empty
        self._max_val = max_val

    def valid(self):
        text = self.get_text()
        if text == '':
            return self._allow_empty
        try:
            val = self._number_cls(text)
        except ValueError:
            return False

        if val < 0:
            return self._allow_neg
        elif val == 0:
            return self._allow_zero
        elif self._max_val:
            return val <= self._max_val
        else:
            return True

    def val(self):
        assert self.valid()
        if self.get_text() == '':
            return None
        else:
            return self._number_cls(self.get_text())

    def set_val(self, val):
        self.set_text(str(val))

class StringEntry(ValidatingEntry):
    def __init__(self, allow_empty=True):
        super(StringEntry, self).__init__()
        self._allow_empty = allow_empty

    def valid(self):
        return bool(self.get_text()) or self._allow_empty

    def val(self):
        return self.get_text()

    def set_val(self, val):
        self.set_text(val)

class UnitNumberEntry(ValidatingEntry):
    def __init__(self, allow_neg=True, allow_empty=False):
        super(UnitNumberEntry, self).__init__()
        self._allow_neg = allow_neg
        self._allow_empty = allow_empty

    def valid(self):
        text = self.get_text()
        if text == '':
            return self._allow_empty
        try:
            val = UnitNumber.from_str(text)
        except ValueError:
            return False

        return val.value >= 0 or self._allow_neg

    def val(self):
        assert self.valid()
        text = self.get_text()
        if text == '':
            return None
        else:
            return UnitNumber.from_str(text)

    def set_val(self, val):
        self.set_text(str(val))

class BoolEntry(gtk.ToggleButton, ValidatingEntry):
    def __init__(self, text="Enable"):
        super(BoolEntry, self).__init__(text)

    def val(self):
        return self.get_active()

    def valid(self):
        return True

    def set_val(self, val):
        self.set_active(val)

def configuration_widget_items(fields):
    widgets = []
    for label, entry_widget, itemdefault in fields:
        label_widget = gtk.Label(label + ": ")
        if itemdefault is not None:
            entry_widget.set_val(itemdefault)
        label_widget.show()
        entry_widget.show()
        widgets.append((label_widget, entry_widget))
    return widgets

def configuration_widget(fields):
    n = len(fields)
    array = gtk.Table(2, n)

    widgets = []
    for idx, (label, entry) in enumerate(configuration_widget_items(fields)):
        array.attach(label, 0, 1, idx, idx + 1)
        array.attach(entry, 1, 2, idx, idx + 1)
        widgets.append(entry)

    array.show()
    return (array, widgets)

def reconfigure(other_widgets):
    return tuple(widget.val() for widget in other_widgets)
