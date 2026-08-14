"""
Chrome styling: the shared look of everything the wrappers draw *around* a form, grid or
list — the title row, its buttons, the title of an embedded section, and the rows of a
ModelList (which is chrome all the way down: the item's own fields are just text in it).

Field styling is a separate cascade and stays where it is (ModelForm's base_props /
default_classes): a field is configured per field, chrome is configured per application.

Two levels, same rule as the field cascade — props are additive (NiceGUI parses them into a
dict, so a later source overwrites a single key), classes replace wholesale:

    set_chrome_style(button_props='dense flat')            # application-wide default
    EditGridWrapper.from_list(..., chrome_style=my_style)  # this wrapper only

The button props ship empty: the chrome decides *where* a button goes and *what it means*
(add, delete, …), the application decides what a button looks like. 'dense flat' for
button_props and 'round' for icon_button_props are the look niceview used before this was
configurable, if you want it back.

`chrome_style=` replaces the default wholesale, so build it from the current default rather
than from scratch if you only want to change one thing:

    EditGridWrapper.from_list(..., chrome_style=get_chrome_style().replace(tooltips=False))
"""
import contextlib
import contextvars
import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Self
from nicegui import ui


@dataclass(frozen=True)
class ChromeStyle:
    """
    The look of the wrapper chrome. Instances are immutable — derive one with replace().

    A button's props are layered base → shape → role: button_props is what every chrome button
    shares, the shape layer depends on whether the button carries a label, and e.g.
    delete_button_props carries only what makes a delete button a delete button. Later layers
    win per key, so a role can override the shape and the shape can override the base.

    Only the role layer carries a default (a delete button is negative — that is meaning, not
    taste). Base and shape are empty until the application fills them in.
    """
    title_row_classes: str = 'w-full items-center flex-nowrap'
    """Classes of the title row (ui.row) of every wrapper."""
    title_classes: str = 'text-h6 grow'
    """Classes of the title label. 'grow' pushes the buttons to the right edge."""
    section_title_classes: str = 'text-subtitle2'
    """Classes of a title *inside* a form: a layout group's card title, or the label of an
    embedded grid. One step below title_classes — it is a section, not the page heading."""

    button_props: str = ''
    """Props shared by every chrome button. Empty: the chrome brings no look of its own, the
    buttons are Quasar's. Set it once for the application, e.g. 'dense flat'."""
    icon_button_props: str = ''
    """Props of a button that shows only its icon (label ''). Its shape follows the button
    itself, not where it sits — except inside a button group, see shape_in_group. Empty;
    'round' is the usual choice."""
    labelled_button_props: str = ''
    """Props of a button that carries a label."""
    shape_in_group: bool = False
    """Whether the shape layer applies inside a ui.button_group as well. Off, because a group
    joins straight edges and a circle has none: 'round' children turn a group into circles with
    a border segment glued on. Turn it on if your shape props survive being joined (Quasar's
    'rounded' does, 'round' does not) — or set button_group=False to get round icon buttons
    everywhere. Joined or round, not both."""
    add_button_props: str = ''
    edit_button_props: str = ''
    delete_button_props: str = 'color=negative'
    save_button_props: str = ''
    refresh_button_props: str = ''
    back_button_props: str = ''

    button_group: bool = True
    """Whether chrome buttons that show at the same time are joined in a ui.button_group."""
    button_group_style: str = 'width: fit-content; flex: none'
    """Inline style of that group — it must not stretch or shrink with the title."""
    button_row_classes: str = 'flex items-center gap-1 w-fit flex-none'
    """Classes of the container used instead of the group: for a single button, or when
    button_group is off. Same job as button_group_style — hold the buttons at their own width
    at the right edge — plus the gap the group does not need."""

    tooltips: bool = True
    """Whether the chrome buttons carry their default tooltips."""

    list_props: str = 'dense separator'
    """Props of a ModelList's ui.list."""
    list_item_classes: str = 'cursor-pointer'
    """Classes of one ui.item. The list rows are clickable, hence the pointer."""
    list_title_props: str = ''
    """Props of an item's title ui.item_label."""
    list_subtitle_props: str = 'caption'
    """Props of an item's subtitle ui.item_label."""
    list_chevron_icon: str | None = 'chevron_right'
    """Icon at the right edge of a row, hinting at the detail view behind it. None renders no
    icon and no section for it — for a list that is not a drill-down."""
    list_chevron_classes: str = 'text-grey'
    """Classes of that icon."""

    def replace(self, **overrides: Any) -> Self:
        """Return a copy with the given attributes changed."""
        return dataclasses.replace(self, **overrides)


_chrome_style = ChromeStyle()


def get_chrome_style() -> ChromeStyle:
    """The current application-wide chrome style."""
    return _chrome_style


def set_chrome_style(style: ChromeStyle | None = None, **overrides: Any) -> ChromeStyle:
    """
    Set the application-wide chrome style and return it. Call with a complete ChromeStyle, or
    with keyword arguments to change single attributes of the current one:

        set_chrome_style(button_props='dense', tooltips=False)

    Wrappers read the style when they render, so this takes effect for everything rendered
    afterwards — call it once at startup, before the first page is built.
    """
    global _chrome_style
    _chrome_style = (style or _chrome_style).replace(**overrides)
    return _chrome_style


def chrome_row(style: ChromeStyle) -> ui.row:
    """The title row shared by all wrappers. Use as a context manager."""
    return ui.row().classes(style.title_row_classes)


def chrome_title(text: str, style: ChromeStyle) -> ui.label:
    """The title label of a wrapper."""
    return ui.label(text).classes(style.title_classes)


_in_button_group: contextvars.ContextVar[bool] = contextvars.ContextVar('niceview_in_button_group', default=False)
"""Set by chrome_buttons() for the buttons built inside it, read by chrome_button() to decide
whether the shape layer applies. Not a parameter of chrome_button(): the buttons are built by
the caller inside the `with`, and threading a flag through every call site would state the
same fact four times per wrapper."""


@contextlib.contextmanager
def chrome_buttons(style: ChromeStyle, count: int) -> Iterator[ui.element]:
    """
    The container for the chrome buttons.

    `count` is how many of them are visible *at the same time* — not how many the wrapper
    builds. Quasar styles a button group as one joined control (squared-off inner edges, a
    shared border), which only says something with a second button to join: a group of one
    is a button wearing a group's clothes. So one button, or button_group=False, goes into a
    plain flex container instead.
    """
    grouped = style.button_group and count > 1
    token = _in_button_group.set(grouped)
    try:
        if grouped:
            with ui.button_group().style(style.button_group_style) as container:
                yield container
        else:
            with ui.element('div').classes(style.button_row_classes) as container:
                yield container
    finally:
        _in_button_group.reset(token)


def chrome_button(kind: str, label: str, icon: str, tooltip: str, style: ChromeStyle,
                  on_click: Callable[..., Any] | None = None) -> ui.button:
    """
    One chrome button, built from three layers of props: the shared button_props, the shape the
    label asks for (round without one, plain with), and the props of this `kind` ('add',
    'delete', …). `label` is the caller's '' (icon only) or its own text.

    The shape depends on the button, not on where it is used — with the one exception Quasar
    imposes: inside a button group there is nothing to round, so the layer is skipped there
    unless the style says otherwise.
    """
    shape = style.labelled_button_props if label else style.icon_button_props
    if _in_button_group.get() and not style.shape_in_group:
        shape = ''
    props = ' '.join(p for p in (style.button_props, shape, getattr(style, f'{kind}_button_props')) if p)
    button = ui.button(label, icon=icon).props(props)
    if on_click is not None:
        button.on_click(on_click)
    if style.tooltips and tooltip:
        with button:
            ui.tooltip(tooltip).style('width: fit-content')
    return button
