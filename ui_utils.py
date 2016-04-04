import pygtk
pygtk.require('2.0')
import gtk

from units import UnitNumber

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

def do_configuration(primitive):
    print("Reconfigure %r" % primitive)
    dialog = gtk.Dialog("Configure")
    widget_info = primitive.reconfiguration_widget()
    print widget_info
    if not widget_info:
        return False
    ((widget, widgets), validator) = widget_info
    if not validator:
        validator = lambda: all(widget.valid() for widget in widgets)
    dialog.get_content_area().add(widget)
    dialog.add_button("Ok", 1)
    dialog.add_button("Cancel", 2)
    parent = primitive.parent()
    if parent is not None:
        dialog.add_button("Edit parent", 3)

    ret = False
    while True:
        result = dialog.run()
        if result == 1:
            if not validator():
                continue
            primitive.reconfigure(widget, widgets)
            ret = True
        dialog.destroy()
        if result == 3:
            ret = do_configuration(parent)
        break
    return ret

def horiz_arrow(cr, x1, x2, y, l_arrowhead=False, r_arrowhead=True,
                thickness=2):
    if x1 < x2:
        mult = 1
    else:
        mult = -1

    cr.move_to(x1, y)
    cr.line_to(x2, y)

    if r_arrowhead:
        cr.move_to(x2, y)
        cr.line_to(x2 - mult * thickness, y + thickness)
        cr.move_to(x2, y)
        cr.line_to(x2 - mult * thickness, y - thickness)
    if l_arrowhead:
        cr.move_to(x1, y)
        cr.line_to(x1 + mult * thickness, y + thickness)
        cr.move_to(x1, y)
        cr.line_to(x1 + mult * thickness, y - thickness)

    cr.stroke()

def vert_arrow(cr, x, y1, y2, t_arrowhead=False, b_arrowhead=True,
               thickness=2):
    if y1 < y2:
        mult = 1
    else:
        mult = -1

    cr.move_to(x, y1)
    cr.line_to(x, y2)

    if b_arrowhead:
        cr.move_to(x, y2)
        cr.line_to(x + thickness, y2 - mult * thickness)
        cr.move_to(x, y2)
        cr.line_to(x - thickness, y2 - mult * thickness)
    if t_arrowhead:
        cr.move_to(x, y1)
        cr.line_to(x + thickness, y1 + mult * thickness)
        cr.move_to(x, y1)
        cr.line_to(x - thickness, y1 + mult * thickness)

    cr.stroke()

def set_dampened_color(cr, r, g, b, dampening):
    cr.set_source_rgb(
        r * (1 - dampening) + dampening,
        g * (1 - dampening) + dampening,
        b * (1 - dampening) + dampening,
    )
