import pygtk
pygtk.require('2.0')
import gtk

def configuration_widget_items(fields):
    widgets = []
    for label, itemty, itemdefault in fields:
        label_widget = gtk.Label(label + ": ")
        # TODO: other types
        entry_widget = gtk.Entry()
        if itemdefault is not None:
            entry_widget.set_text(str(itemdefault))
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
    return tuple(
        widget.get_text() if widget.get_text() != '' else None
        for widget in other_widgets
    )
