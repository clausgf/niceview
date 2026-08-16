"""
Chrome styling: the shared look of everything the wrappers draw *around* a form, grid or
list — the title row, its buttons, the dialogs, the title of an embedded section, and the rows
of a ModelList (which is chrome all the way down: the item's own fields are just text in it).

Two axes, because they are orthogonal — every chrome button sits in exactly one **place** and
carries exactly one **role**:

    {place}_button_props  →  shape  →  {role}_button_props

The place is where the button sits ('toolbar' at the top level, 'form' for a widget embedded
in a form, 'dialog' in a dialog footer). The shape follows the button itself — icon-only or
labelled — and a place may override it. The role is what the button means (add, delete, ok, …)
and has the last word.

There is deliberately no base layer below the places: "every button of this application looks
like that" is a type statement, and NiceGUI already owns it —
`ui.button.default_props('dense flat')`. niceview only styles what NiceGUI cannot see.

Field styling is the second cascade (FieldStyle below). It is separate because it is keyed by
widget *category*, not by place or role — but it follows the same idea: an application-wide
default, a per-form layer, and the field itself.

Merge semantics, readable off the type:

    str          additive layer — props merge per key, the later layer wins
    str | None   replacing layer — None inherits, '' suppresses, a value replaces
    *_classes    replaces wholesale (a CSS class has no key to merge on)

    set_chrome_style(toolbar_button_props='dense flat')       # application-wide default
    EditGridWrapper.from_list(..., chrome_style=ChromeStyle.derived(tooltips=False))
"""
import contextlib
import contextvars
import dataclasses
from dataclasses import dataclass
from typing import Any, Callable, Iterator, Literal, Self
from nicegui import ui


Place = Literal['toolbar', 'form', 'dialog']
"""Where a chrome button sits. 'toolbar' is a wrapper's own action row, 'form' the same row for
a wrapper embedded in a form, 'dialog' a dialog footer. A ModelList row and a ModelGrid row are
not places: the list row navigates (that is its whole job) and a grid cell lives client-side in
AG Grid, where Quasar props do not reach."""

NotifyKind = Literal['positive', 'negative', 'warning', 'info']
"""Quasar's notification types. `type=` rather than `color=`: it brings the matching icon."""

NotifyPosition = Literal['top-left', 'top-right', 'bottom-left', 'bottom-right',
                         'top', 'bottom', 'left', 'right', 'center']
"""Where a notification appears — NiceGUI's own set of positions."""


@dataclass(frozen=True)
class ChromeStyle:
    """
    The look of the wrapper chrome. Instances are immutable — derive one with replace(), or
    from the application-wide default with ChromeStyle.derived().
    """
    title_row_classes: str = 'w-full items-center flex-nowrap'
    """Classes of the title row (ui.row) of every wrapper."""
    title_classes: str = 'text-h6 grow'
    """Classes of the title label. 'grow' pushes the buttons to the right edge."""
    card_title_classes: str = 'text-subtitle2'
    """Classes of a layout section's title that draws a card ('# …')."""
    section_title_classes: str = 'text-subtitle2'
    """Classes of a title *inside* a form without a card ('## …'), and of the label of an
    embedded grid. One step below title_classes — it is a section, not the page heading."""

    # --- place layer -------------------------------------------------------
    toolbar_button_props: str = ''
    """Props of the buttons in a wrapper's own action row. Empty: the chrome brings no look of
    its own, the buttons are Quasar's. Set it once for the application, e.g. 'dense flat'."""
    form_button_props: str = ''
    """Props of the buttons of a wrapper embedded in a form — chrome of a section, not of a
    page. Falls back to nothing, not to toolbar_button_props: the places are separate."""
    dialog_button_props: str = ''
    """Props of the buttons in a dialog footer."""

    # --- shape layer -------------------------------------------------------
    icon_button_props: str = ''
    """Props of a button that shows only its icon (label ''). Its shape follows the button
    itself, not where it sits — except inside a button group, see shape_in_group, and where a
    place overrides it below. Empty; 'round' is the usual choice."""
    labelled_button_props: str = ''
    """Props of a button that carries a label."""
    toolbar_icon_button_props: str | None = None
    """Icon shape in the toolbar. None inherits icon_button_props, '' suppresses the shape
    entirely, a value replaces it. Replacing rather than adding, because Quasar's shapes are
    separate boolean props: 'round' and 'rounded' are two keys, so a later layer cannot cancel
    an earlier one by setting a different one."""
    form_icon_button_props: str | None = None
    """Icon shape for a wrapper embedded in a form. See toolbar_icon_button_props."""
    dialog_icon_button_props: str | None = None
    """Icon shape in a dialog footer. See toolbar_icon_button_props."""
    shape_in_group: bool = False
    """Whether the shape layer applies inside a ui.button_group as well. Off, because a group
    joins straight edges and a circle has none: 'round' children turn a group into circles with
    a border segment glued on. Turn it on if your shape props survive being joined (Quasar's
    'rounded' does, 'round' does not) — or set button_group=False to get round icon buttons
    everywhere. Joined or round, not both."""

    # --- role layer --------------------------------------------------------
    add_button_props: str = ''
    edit_button_props: str = ''
    delete_button_props: str = 'color=negative'
    """The only default in the whole style — and only because it is meaning, not taste."""
    save_button_props: str = ''
    refresh_button_props: str = ''
    back_button_props: str = ''
    ok_button_props: str = ''
    cancel_button_props: str = ''

    button_group: bool = True
    """Whether chrome buttons that show at the same time are joined in a ui.button_group."""
    button_group_style: str = 'width: fit-content; flex: none'
    """Inline style of that group — it must not stretch or shrink with the title."""
    button_row_classes: str = 'flex items-center gap-1 w-fit flex-none'
    """Classes of the container used instead of the group: for a single button, or when
    button_group is off. Same job as button_group_style — hold the buttons at their own width
    at the right edge — plus the gap the group does not need."""

    tooltips: bool = True
    """Whether the chrome buttons carry their default tooltips. What those tooltips *say* is
    niceview.text.ChromeText."""

    # --- dialogs -----------------------------------------------------------
    dialog_props: str = ':maximized="$q.screen.lt.md" transition-show="slide-up" transition-hide="slide-down"'
    """Props of every dialog niceview opens. Maximized on a small screen, sliding in from the
    bottom — the phone behaviour; a wide screen gets a plain centered card."""
    dialog_style: str = 'width: 400px'
    """Inline style of the dialog."""
    dialog_card_classes: str = 'w-full'
    """Classes of the ui.card inside the dialog."""
    dialog_title_classes: str = 'text-h6'
    """Classes of the dialog's title label."""
    dialog_button_row_classes: str = 'w-full place-content-end'
    """Classes of the dialog's button row: cancel first, confirm last, right-aligned."""

    # --- notifications -----------------------------------------------------
    notify_position: NotifyPosition = 'bottom'
    """Where niceview's notifications appear. Quasar's positions ('top', 'bottom-right', …)."""
    notify_timeout: float = 5.0
    """How long they stay, in seconds. 0 keeps them until dismissed."""
    notify_close_button: bool = False
    """Whether they carry a close button."""
    notify: 'Callable[[str, NotifyKind], None] | None' = None
    """Hook for an application with a notification system of its own: called with the message
    and its kind instead of ui.notify. None uses ui.notify with the three options above."""

    # --- ModelList rows ----------------------------------------------------
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

    @classmethod
    def derived(cls, **overrides: Any) -> 'ChromeStyle':
        """
        The application-wide style with the given attributes changed — the usual way to build
        the `chrome_style=` of a single widget, which *replaces* the default rather than adding
        to it:

            EditGridWrapper.from_list(..., chrome_style=ChromeStyle.derived(button_group=False))

        Deriving is not avoidable by merging a partial style: a fresh dataclass carries
        defaults, not "unset", so ChromeStyle(button_group=False) could not be told apart from
        "every other value deliberately at its default".
        """
        return get_chrome_style().replace(**overrides)


_chrome_style = ChromeStyle()


def get_chrome_style() -> ChromeStyle:
    """The current application-wide chrome style."""
    return _chrome_style


def set_chrome_style(style: ChromeStyle | None = None, **overrides: Any) -> ChromeStyle:
    """
    Set the application-wide chrome style and return it. Call with a complete ChromeStyle, or
    with keyword arguments to change single attributes of the current one:

        set_chrome_style(toolbar_button_props='dense', tooltips=False)

    Wrappers read the style when they render, so this takes effect for everything rendered
    afterwards — call it once at startup, before the first page is built.
    """
    global _chrome_style
    _chrome_style = (style or _chrome_style).replace(**overrides)
    return _chrome_style


# ---------------------------------------------------------------------------
# Field styling
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FieldStyle:
    """
    Application-wide defaults for form fields, by widget *category*.

    Two categories, because that is what the practice asks for: an input and a select take the
    same props, a switch does not ('outlined' says nothing to a checkbox). A category is
    niceview's vocabulary — NiceGUI can only say "every ui.input", which would make the
    application enumerate ten widget types.

    The cascade below this: ModelForm(base_props=…) for one form, FieldInfo(props=…) for one
    field. Props are additive per key, the narrower layer wins; classes replace wholesale.
    """
    input_props: str = ''
    """Props for the QInput/QSelect based widgets — see widgets.INPUT_BASED_WIDGETS."""
    control_props: str = ''
    """Props for checkbox, switch, radio, toggle, checkbox_group, slider, rating —
    see widgets.CONTROL_WIDGETS."""
    default_classes: str = ''
    """Classes for every field that brings none of its own and whose form sets none either."""

    def replace(self, **overrides: Any) -> Self:
        """Return a copy with the given attributes changed."""
        return dataclasses.replace(self, **overrides)

    @classmethod
    def derived(cls, **overrides: Any) -> 'FieldStyle':
        """The application-wide field style with the given attributes changed."""
        return get_field_style().replace(**overrides)


_field_style = FieldStyle()


def get_field_style() -> FieldStyle:
    """The current application-wide field style."""
    return _field_style


def set_field_style(style: FieldStyle | None = None, **overrides: Any) -> FieldStyle:
    """
    Set the application-wide field style and return it:

        set_field_style(input_props='outlined dense', default_classes='w-full')
    """
    global _field_style
    _field_style = (style or _field_style).replace(**overrides)
    return _field_style


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

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
same fact four times per wrapper. The *place*, unlike this, is not derived from the container —
the wrapper knows it and passes it in."""


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


def chrome_button(kind: str | None, label: str, icon: str | None, tooltip: str, style: ChromeStyle,
                  on_click: Callable[..., Any] | None = None, place: Place = 'toolbar') -> ui.button:
    """
    One chrome button, built from three layers of props: the props of its `place`, the shape
    the label asks for (icon-only or labelled), and the props of its `kind` ('add', 'delete',
    …). `label` is the caller's '' (icon only) or its own text.

    The shape depends on the button rather than on where it sits, with two exceptions: a place
    may replace the icon shape (a dialog wants squared-off buttons where a lone toolbar button
    is round), and inside a button group there is nothing to round, so the layer is skipped
    there unless the style says otherwise.

    `kind` is None for an application's own action (niceview.FormAction): the roles are a closed
    vocabulary of what niceview itself means by a button, so an action skips that layer and
    brings its own props instead. Place and shape still apply — it sits among the others.
    """
    if label:
        shape = style.labelled_button_props
    else:
        override: str | None = getattr(style, f'{place}_icon_button_props')
        shape = style.icon_button_props if override is None else override
    if _in_button_group.get() and not style.shape_in_group:
        shape = ''
    role = getattr(style, f'{kind}_button_props') if kind else ''
    layers = (getattr(style, f'{place}_button_props'), shape, role)
    button = ui.button(label, icon=icon).props(' '.join(p for p in layers if p))
    if on_click is not None:
        button.on_click(on_click)
    if style.tooltips and tooltip:
        with button:
            ui.tooltip(tooltip).style('width: fit-content')
    return button


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def chrome_dialog(style: ChromeStyle) -> Iterator[ui.dialog]:
    """
    The shell of every dialog niceview opens: the ui.dialog and the ui.card inside it, entered
    as the current context. The caller fills the card and awaits the yielded dialog.
    """
    dialog = ui.dialog().props(style.dialog_props).style(style.dialog_style)
    with dialog, ui.card().classes(style.dialog_card_classes):
        yield dialog


def chrome_dialog_title(text: str, style: ChromeStyle) -> ui.label:
    """The title label of a dialog."""
    return ui.label(text).classes(style.dialog_title_classes)


def chrome_dialog_buttons(style: ChromeStyle) -> ui.row:
    """The button row of a dialog. Use as a context manager: cancel first, confirm last."""
    return ui.row().classes(style.dialog_button_row_classes)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def chrome_notify(message: str, kind: NotifyKind, style: ChromeStyle) -> None:
    """
    Show one of niceview's notifications. Routed to the style's `notify` hook if the
    application brought one, otherwise to ui.notify with the style's options.

    `kind` is Quasar's semantic type, not a color — niceview never spells a color of its own.
    """
    if style.notify is not None:
        style.notify(message, kind)
        return
    ui.notify(message, type=kind, position=style.notify_position,
              timeout=style.notify_timeout, close_button=style.notify_close_button)
