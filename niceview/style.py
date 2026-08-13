"""
Chrome styling: the shared look of everything the wrappers draw *around* a form, grid or
list — the title row, its buttons, the title of an embedded section, and the rows of a
ModelList (which is chrome all the way down: the item's own fields are just text in it).

Field styling is a separate cascade and stays where it is (ModelForm's base_props /
default_classes): a field is configured per field, chrome is configured per application.

Two levels, same rule as the field cascade — props are additive (NiceGUI parses them into a
dict, so a later source overwrites a single key), classes replace wholesale:

    set_chrome_style(button_props='dense')                 # application-wide default
    EditGridWrapper.from_list(..., chrome_style=my_style)  # this wrapper only

`chrome_style=` replaces the default wholesale, so build it from the current default rather
than from scratch if you only want to change one thing:

    EditGridWrapper.from_list(..., chrome_style=get_chrome_style().replace(tooltips=False))
"""
import contextlib
import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Self
from nicegui import ui


@dataclass(frozen=True)
class ChromeStyle:
    """
    The look of the wrapper chrome. Instances are immutable — derive one with replace().

    The per-button props are merged *on top of* button_props, so button_props is the base
    every chrome button shares and e.g. delete_button_props only carries what makes a delete
    button different.
    """
    title_row_classes: str = 'w-full items-center flex-nowrap'
    """Classes of the title row (ui.row) of every wrapper."""
    title_classes: str = 'text-h6 grow'
    """Classes of the title label. 'grow' pushes the buttons to the right edge."""
    section_title_classes: str = 'text-subtitle2'
    """Classes of a title *inside* a form: a layout group's card title, or the label of an
    embedded grid. One step below title_classes — it is a section, not the page heading."""

    button_props: str = 'dense flat'
    """Props shared by every chrome button."""
    add_button_props: str = ''
    edit_button_props: str = ''
    delete_button_props: str = 'color=negative'
    save_button_props: str = ''
    refresh_button_props: str = ''
    back_button_props: str = ''

    button_group: bool = True
    """Whether the chrome buttons are joined in a ui.button_group."""
    button_group_style: str = 'width: fit-content; flex: none'
    """Inline style of that group — it must not stretch or shrink with the title."""

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


@contextlib.contextmanager
def chrome_button_group(style: ChromeStyle) -> Iterator[ui.element | None]:
    """
    The container for the chrome buttons: a ui.button_group, or nothing at all when the style
    turns it off — in which case the buttons land in the enclosing row, spaced by its gap.
    """
    if not style.button_group:
        yield None
        return
    with ui.button_group().style(style.button_group_style) as group:
        yield group


def chrome_button(kind: str, label: str, icon: str, tooltip: str, style: ChromeStyle,
                  on_click: Callable[..., Any] | None = None) -> ui.button:
    """
    One chrome button: `kind` ('add', 'delete', …) selects the per-kind props merged on top of
    the shared button_props, and label is the caller's '' (icon only) or its own text.
    """
    props = ' '.join(p for p in (style.button_props, getattr(style, f'{kind}_button_props')) if p)
    button = ui.button(label, icon=icon).props(props)
    if on_click is not None:
        button.on_click(on_click)
    if style.tooltips and tooltip:
        with button:
            ui.tooltip(tooltip).style('width: fit-content')
    return button
