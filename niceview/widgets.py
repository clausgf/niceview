"""
Model-free widget layer: one NiceGUI widget from one FieldInfo.

`render_field()` builds and styles a widget, `field_value()` reads it back and converts the
value to its Python type. Neither needs a Pydantic model, so callers that decide for
themselves what a field is — an interpreter for an untrusted schema, a hand-built form —
get niceview's widgets, styling and value conversions without `create_model()`.

ModelForm is built on the same functions: it calls `create_widget()` with a value getter of
its own and then wires change handlers, validation state and item binding on top. Both paths
therefore render identical widgets.

Not supported here: 'editgrid' and 'modelselect'. Both need a model type and a repository, so
they only exist inside ModelForm.
"""
import contextlib
import datetime
import inspect
import logging
import types
import typing
from typing import Any, Callable
from zoneinfo import ZoneInfo

from pydantic import SecretStr, TypeAdapter

from nicegui import background_tasks, ui
from nicegui.elements.mixins.validation_element import ValidationDict, ValidationFunction
from nicegui.events import Handler, ValueChangeEventArguments, handle_event

from niceview.fieldinfo import FieldInfo, _merge_field_infos
from niceview.style import get_field_style
from niceview.text import get_chrome_text, text_of

log = logging.getLogger('niceview')


MODEL_ONLY_WIDGETS: tuple[str, ...] = ('editgrid', 'modelselect')
"""Widget types that need a model type and a repository — ModelForm only, not render_field()."""

class _FromChromeText:
    """Sentinel for a text that is taken from niceview.text.ChromeText when the widget is
    built. Not a constant with the English string in it: ChromeText is the single place where
    niceview's texts live, and a default evaluated at import time could not follow a later
    set_chrome_text()."""

    def __repr__(self) -> str:
        return 'FROM_CHROME_TEXT'


FROM_CHROME_TEXT = _FromChromeText()
"""Default of the `required_marker` / `required_message` arguments: use ChromeText. Pass an
explicit string to override it here, or None (for the marker) to render none."""

DescriptionTarget: typing.TypeAlias = typing.Literal['hint', 'tooltip'] | None
"""Where a model's `description` is rendered: below the widget, on hover, or nowhere."""

DESCRIPTION_AS: DescriptionTarget = 'tooltip'
"""Default slot for a field's `description`. Per form: ModelForm(description_as=...); per call:
render_field(..., description_as=...). 'tooltip' rather than 'hint' because every widget has a
tooltip, while a hint needs one of HINT_WIDGETS — and because a hint costs vertical space in
every row, whereas a description is supplementary by nature. A field that sets `hint` or
`tooltip` explicitly is never touched by this."""

HINT_WIDGETS: frozenset[str] = frozenset({
    'ui.input', 'ui.number', 'ui.textarea', 'ui.select', 'ui.input_chips', 'ui.color_input',
    'datetime', 'date', 'time', 'timedelta', 'modelselect',
})
"""Widget types with a Quasar hint slot below the field (all QInput/QSelect based)."""

INPUT_BASED_WIDGETS: frozenset[str] = frozenset({
    'ui.input', 'ui.number', 'ui.textarea', 'ui.select', 'ui.input_chips', 'ui.color_input',
    'datetime', 'date', 'time', 'timedelta', 'modelselect',
})
"""Widget types built on a Quasar QInput/QSelect — the ones that take 'outlined', 'filled',
'standout' and friends. FieldStyle.input_props styles them. Deliberately its own list rather
than an alias of HINT_WIDGETS: that the two happen to hold the same types today says nothing
about the two questions ("does it have a hint slot" and "which props does it accept")."""

CONTROL_WIDGETS: frozenset[str] = frozenset({
    'ui.checkbox', 'ui.switch', 'ui.radio', 'ui.toggle', 'checkbox_group',
    'ui.slider', 'ui.rating',
})
"""Widget types that are not built on a QInput — a prop like 'outlined' says nothing to them.
FieldStyle.control_props styles them. 'editgrid' is in neither list: it brings its own chrome
rather than being a field with props."""

CAPTION_WIDGETS: frozenset[str] = frozenset({
    'ui.radio', 'ui.toggle', 'checkbox_group', 'ui.slider', 'ui.rating',
})
"""Widget types with no label of their own; niceview renders a caption above them instead."""

TEXT_INPUT_WIDGETS: frozenset[str] = frozenset({
    'ui.input', 'ui.number', 'ui.textarea', 'ui.input_chips',
    'datetime', 'date', 'time', 'timedelta',
})
"""Widget types that edit text: validate while typing, commit on blur (ModelForm wiring)."""

CLEARABLE_PROP_WIDGETS: frozenset[str] = frozenset({
    'ui.input', 'ui.number', 'ui.textarea', 'ui.color_input',
    'datetime', 'date', 'time', 'timedelta',
})
"""Widget types that take `clearable` as a Quasar prop rather than as a NiceGUI argument.
ui.select, ui.toggle and ui.input_chips have a constructor argument for it; the QInput based
ones here do not, but the q-input underneath honours the prop just the same. Clearing writes
None into the field, so the model has to accept it — `clearable` says nothing about the type."""

VALIDATED_WIDGETS: frozenset[str] = TEXT_INPUT_WIDGETS | frozenset({'ui.select', 'modelselect'})
"""Widget types with a visible validation message. For the rest (checkbox, switch, radio,
toggle, slider, rating, ...) an error message has nowhere to go."""


WIDGET_OPTIONS: dict[str, dict[str, frozenset[str]]] = {
    # Every constructor argument of every supported NiceGUI element, in exactly one bucket:
    #   field_info — carried by a FieldInfo attribute of the same name (renames noted below)
    #   owned      — set by niceview itself (the value, the change handling)
    #   via_props  — deliberately not a FieldInfo attribute; reachable through props=
    # tests/test_widget_option_coverage.py checks this against the installed NiceGUI, so an
    # upgrade that adds an argument fails loudly instead of drifting silently.
    # The table reads from NiceGUI's side: a FieldInfo attribute may reach a widget that has no
    # argument for it as a Quasar prop instead, and then appears in no bucket here — see
    # CLEARABLE_PROP_WIDGETS.
    'ui.input': {'field_info': frozenset({'label', 'placeholder', 'password', 'password_toggle_button', 'autocomplete', 'prefix', 'suffix', 'validation'}),
                 'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.number': {'field_info': frozenset({'label', 'placeholder', 'min', 'max', 'precision', 'step', 'prefix', 'suffix', 'format', 'validation'}),
                  'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.textarea': {'field_info': frozenset({'label', 'placeholder', 'validation'}),
                    'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.checkbox': {'field_info': frozenset({'text'}),  # fed from label
                    'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.switch': {'field_info': frozenset({'text'}),
                  'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.select': {'field_info': frozenset({'label', 'options', 'with_input', 'new_value_mode', 'multiple', 'clearable', 'validation', 'key_generator'}),
                  'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.radio': {'field_info': frozenset({'options'}),
                 'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.toggle': {'field_info': frozenset({'options', 'clearable'}),
                  'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.color_input': {'field_info': frozenset({'label', 'placeholder', 'preview'}),  # preview <- color_preview
                       'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.input_chips': {'field_info': frozenset({'label', 'new_value_mode', 'clearable', 'validation'}),
                       'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.slider': {'field_info': frozenset({'min', 'max', 'step'}),
                  'owned': frozenset({'value', 'on_change'}), 'via_props': frozenset()},
    'ui.rating': {'field_info': frozenset({'max'}),
                  'owned': frozenset({'value', 'on_change'}),
                  'via_props': frozenset({'icon', 'icon_selected', 'icon_half', 'color', 'size'})},
}
"""The FieldInfo <-> NiceGUI option contract, per widget type. See tests/test_widget_option_coverage.py."""


def _pick_attrs(obj: Any, attrs: list[str], rename: dict[str, str] = {}) -> dict[str, Any]:
    """
    Return a dict of non-None attribute values from obj for the given attribute names.
    `rename` maps a FieldInfo attribute name to the NiceGUI keyword it is passed as, for the
    few places where the two deliberately differ (number_format -> format).
    """
    return {rename.get(k, k): v for k in attrs if (v := getattr(obj, k)) is not None}


def _label(field_info: FieldInfo, required_marker: str | None) -> str:
    """The widget's label: the FieldInfo label plus the required marker. Empty label = no label."""
    label = field_info.label or ''
    if label and field_info.required and required_marker:
        label += required_marker
    return label


@contextlib.contextmanager
def _labelled(field_info: FieldInfo, required_marker: str | None, classes: str = 'gap-1') -> 'typing.Iterator[ui.column]':
    """
    Context manager for the widgets that have no label parameter of their own (radio, toggle,
    checkbox_group, slider, rating): a column with a caption above the widget. NiceGUI leaves
    these unlabelled; a form in which some fields have no label is not a form.
    """
    with ui.column().classes(classes) as column:
        if label := _label(field_info, required_marker):
            ui.label(label).classes(get_field_style().caption_classes)
        yield column


class CheckboxGroup:
    """
    Composite widget for list[Literal[...]] fields rendered as a row/column of ui.checkbox
    elements. There is no built-in NiceGUI/Quasar multi-select checkbox-group widget, so this
    composes plain ui.checkbox elements and exposes the .value / on_value_change() surface that
    ModelForm's value-conversion and event-wiring code expects from a widget.

    `checkboxes` (options -> ui.checkbox) and `widget` (the ui.row/ui.column holding them)
    are public so callers can style individual checkboxes or the container after rendering,
    e.g. `form.w('perms', CheckboxGroup).checkboxes['admin'].classes('text-negative')`.
    """

    def __init__(self, options: list[Any], checkboxes: dict[Any, ui.checkbox], widget: ui.element) -> None:
        self.options = options
        self.checkboxes = checkboxes
        self.widget = widget
        self._value_change_handlers: list[Handler[ValueChangeEventArguments]] = []
        self._disabled = False
        for checkbox in self.checkboxes.values():
            checkbox.on_value_change(self._relay)

    @property
    def value(self) -> list[Any]:
        return [opt for opt in self.options if self.checkboxes[opt].value]

    @value.setter
    def value(self, new_value: list[Any] | None) -> None:
        selected = set(new_value or [])
        for opt, checkbox in self.checkboxes.items():
            checkbox.value = opt in selected

    @property
    def parent_slot(self) -> Any:
        # nicegui.events.handle_event() needs this to run the handler in the right UI context.
        return self.widget.parent_slot

    @property
    def client(self) -> Any:
        return self.widget.client

    def on_value_change(self, handler: Handler[ValueChangeEventArguments]) -> None:
        self._value_change_handlers.append(handler)

    # Styling is forwarded to the container, mirroring what apply_field_info() does to a native
    # widget: ui.radio also gets the classes itself, not the caption column wrapping it.

    def classes(self, add: str | None = None, **kwargs: Any) -> 'CheckboxGroup':
        self.widget.classes(add, **kwargs)
        return self

    def style(self, add: str | None = None, **kwargs: Any) -> 'CheckboxGroup':
        self.widget.style(add, **kwargs)
        return self

    def props(self, add: str | None = None, **kwargs: Any) -> 'CheckboxGroup':
        self.widget.props(add, **kwargs)
        return self

    def tooltip(self, text: str) -> 'CheckboxGroup':
        self.widget.tooltip(text)
        return self

    def _relay(self, e: ValueChangeEventArguments) -> None:
        vce = ValueChangeEventArguments(sender=self, client=e.client, value=self.value, previous_value=None)  # type: ignore[arg-type]
        for handler in self._value_change_handlers:
            handle_event(handler, vce)

    def set_options(self, options: 'list | dict') -> None:
        """Replace the checkboxes with a new option set, keeping the current selection where possible."""
        items = list(options.items()) if isinstance(options, dict) else [(opt, opt) for opt in options]
        selected = set(self.value)
        self.widget.clear()
        self.checkboxes = {}
        with self.widget:
            for opt, label in items:
                # initial value in the constructor does not fire on_value_change
                checkbox = ui.checkbox(text=str(label), value=opt in selected)
                checkbox.on_value_change(self._relay)
                self.checkboxes[opt] = checkbox
        self.options = [opt for opt, _ in items]
        if self._disabled:
            self.disable()

    def disable(self) -> None:
        self._disabled = True
        for checkbox in self.checkboxes.values():
            checkbox.disable()


# --- validation ------------------------------------------------------------

def is_empty(value: Any) -> bool:
    """
    True for the values a required field rejects: None, the empty string and an empty
    collection. Deliberately not `not value`: a required switch may be False and a required
    number may be 0.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value == ''
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def required_error(field_info: FieldInfo, value: Any,
                   message: 'str | _FromChromeText' = FROM_CHROME_TEXT) -> str | None:
    """
    Validation layer 1a: reject an empty value in a required field. Works without a model, so
    a JSON-Schema `required` means the same thing as a Pydantic field without a default.
    Skipped for non-editable fields — a disabled empty field must not block a form forever.
    """
    if field_info.required and field_info.editable and is_empty(value):
        return text_of(get_chrome_text().required_message) if isinstance(message, _FromChromeText) else message
    return None


def run_validation(validation: 'ValidationFunction | ValidationDict | None', value: Any) -> 'str | None | typing.Awaitable[str | None]':
    """
    Validation layer 1b: run a NiceGUI validation as NiceGUI would.
    A callable returns the message (or an awaitable of one); a dict maps message -> predicate
    and yields the first failing message. Returns None when the value is acceptable.
    """
    if validation is None:
        return None
    if callable(validation):
        return validation(value)
    for message, check in validation.items():
        if not check(value):
            return message
    return None


# --- type helpers ----------------------------------------------------------

def _field_allows_none(field_type: Any) -> bool:
    """True if field_type is Optional / a Union that includes None."""
    if typing.get_origin(field_type) is typing.Union or isinstance(field_type, types.UnionType):
        return type(None) in typing.get_args(field_type)
    return False


def _unwrap_optional(field_type: Any) -> Any:
    """Return the single non-None member of an Optional/Union, else field_type unchanged."""
    if typing.get_origin(field_type) is typing.Union or isinstance(field_type, types.UnionType):
        non_none = [t for t in typing.get_args(field_type) if t is not type(None)]
        if len(non_none) == 1:
            return non_none[0]
    return field_type


# --- options ---------------------------------------------------------------

def _resolve_options(name: str, field_info: FieldInfo) -> 'tuple[Any, typing.Awaitable | None]':
    """
    Resolve options for select/radio/toggle/checkbox_group widgets from field_info.
    Resolution order: field_info.options, then literal_options (auto-extracted from
    Literal[...] types). A callable source is invoked; it may be sync or async.
    Returns (options, pending): for a sync source pending is None; for an async source
    options is [] and pending is the awaitable — the caller schedules it via
    _schedule_late_options().
    """
    raw = field_info.options or field_info.literal_options
    if not raw:
        raise ValueError(f"Field '{name}' has no options (or literal_options) defined in FieldInfo")
    value = raw() if callable(raw) else raw
    if inspect.isawaitable(value):
        return [], value
    return value, None


def _schedule_late_options(name: str, pending: 'typing.Awaitable', apply: Callable[[Any], None]) -> None:
    """Await an async options source in the background and apply the result to the widget."""
    async def _later() -> None:
        apply(await pending)
    background_tasks.create(_later(), name=f'niceview options for {name}')


def _make_late_options_applier(widget: Any, push_value: Callable[[Any], None]) -> Callable[[Any], None]:
    """Return a callback that sets late-arriving options and re-pushes the current value."""
    def apply(options: Any) -> None:
        widget.set_options(options)
        push_value(widget)
    return apply


# --- value conversion ------------------------------------------------------

def to_widget_value(field_info: FieldInfo, value: Any, *, local_tz: str | None = None) -> Any:
    """
    Convert a Python value to the representation its widget expects.

    date / time / datetime / timedelta become ISO strings (a value that already is a string is
    passed through unchanged, so JSON-sourced data works without pre-conversion); a None
    multi-selection becomes an empty list. Everything else is returned unchanged.

    'modelselect' is not handled here — the key lookup needs a repository (see ModelForm).
    """
    widget_type = field_info.widget_type

    if widget_type == 'ui.select' and field_info.multiple:
        # A multi-select widget expects a list; map a None model value to [].
        if value is None:
            value = []

    elif widget_type == 'checkbox_group':
        # Always multi-valued by construction; map a None model value to [].
        if value is None:
            value = []

    elif widget_type == 'datetime':
        if isinstance(value, str):
            pass  # already an ISO string (e.g. from JSON) — the widget takes it verbatim
        elif value is not None:
            tz = ZoneInfo(local_tz) if local_tz else None
            value = value.astimezone(tz).replace(tzinfo=None, microsecond=0).isoformat()
        else:
            value = ''

    elif widget_type == 'date':
        if isinstance(value, str):
            pass
        else:
            value = value.isoformat() if value is not None else ''

    elif widget_type == 'time':
        if isinstance(value, str):
            pass
        else:
            value = value.replace(microsecond=0).isoformat() if value is not None else ''

    elif widget_type == 'timedelta':
        if not isinstance(value, str):
            timedelta_adapter = TypeAdapter(datetime.timedelta)
            value = timedelta_adapter.dump_python(value, mode="json")

    if isinstance(value, SecretStr):
        # The widget edits the plain text; field_value() wraps it up again.
        value = value.get_secret_value()

    return value


def field_value(widget: Any, field_info: FieldInfo, *, local_tz: str | None = None) -> Any:
    """
    Read a widget rendered by render_field() and convert its value to the field's Python type.

    The inverse of the value handling in render_field(): ISO strings become date / time /
    datetime / timedelta objects, numbers become int or float according to
    `field_info.field_type`, comma-separated chips are split.

    `field_info.field_type` (default `str`) drives the conversions that depend on the target
    type — set it to `int` to get ints out of a 'ui.number', to `list[str]` for a
    comma-separated 'ui.input', or to `T | None` to have an empty selection read back as None.

    Raises ValueError for 'editgrid' and 'modelselect', which need a model and a repository.
    """
    widget_type = field_info.widget_type
    if not widget_type:
        raise ValueError("field_value() requires field_info.widget_type to be set")
    if widget_type in MODEL_ONLY_WIDGETS:
        raise ValueError(f"field_value() does not support widget_type '{widget_type}': it needs a model repository (use ModelForm)")

    field_type = field_info.field_type
    value = widget.value

    if widget_type == 'ui.select' and field_info.multiple:
        # Map an empty multi-select back to None when the field is Optional,
        # so Optional[list[...]] round-trips without special-casing elsewhere.
        if not value and _field_allows_none(field_type):
            value = None

    elif widget_type == 'checkbox_group':
        # Same None <-> [] interchangeability as the ui.select multi-select case.
        if not value and _field_allows_none(field_type):
            value = None

    elif widget_type == 'ui.input' and typing.get_origin(field_type) == list:
        value = [item.strip() for item in value.split(',')]
        item_type = field_info.item_type
        if item_type in (int, float, bool, str):
            value = [item_type(item) for item in value]  # type: ignore[misc]
        else:
            raise ValueError("Field is a list but no allowed item type is specified")

    elif widget_type == 'ui.number':
        # A cleared number field yields None (or ''); map it back to None so
        # Optional fields round-trip and required fields fail validation cleanly,
        # instead of int(None)/float(None) raising and leaving a stale value.
        if value is None or value == '':
            value = None
        elif _unwrap_optional(field_type) == int:
            value = int(value)
        else:
            value = float(value)

    elif widget_type in ('ui.slider', 'ui.rating'):
        if _unwrap_optional(field_type) == int:
            value = int(value) if value is not None else 0
        else:
            value = float(value) if value is not None else 0.0

    elif widget_type == 'ui.input_chips':
        expanded: list[Any] = []
        for v in value:
            if isinstance(v, str) and ',' in v:
                expanded.extend(item.strip() for item in v.split(','))
            else:
                expanded.append(v)
        value = expanded

    elif widget_type == 'datetime':
        if value:
            dt = datetime.datetime.fromisoformat(value)
            tz = ZoneInfo(local_tz) if local_tz else None
            value = dt.replace(tzinfo=tz).astimezone(datetime.timezone.utc)
        else:
            value = None

    elif widget_type == 'date':
        value = datetime.date.fromisoformat(value) if value else None

    elif widget_type == 'time':
        value = datetime.time.fromisoformat(value) if value else None

    elif widget_type == 'timedelta':
        timedelta_adapter = TypeAdapter(datetime.timedelta)
        value = timedelta_adapter.validate_python(value)

    if _unwrap_optional(field_type) is SecretStr and value is not None:
        value = SecretStr(value)

    return value


# --- widget creation -------------------------------------------------------

def resolve_help_texts(field_info: FieldInfo, description_as: DescriptionTarget = DESCRIPTION_AS) -> tuple[str | None, str | None]:
    """
    The (hint, tooltip) texts to render for a field.

    What the field sets explicitly is used as-is. The model's `description` fills whichever of
    the two `description_as` names — but only if the field left that one unset, and never the
    other one. 'Unset' means the attribute was never assigned, so `Field(tooltip='')` is a way
    to say 'no tooltip here, not even from the description'.
    """
    hint, tooltip = field_info.hint, field_info.tooltip
    if field_info.description:
        if description_as == 'hint' and 'hint' not in vars(field_info):
            hint = field_info.description
        elif description_as == 'tooltip' and 'tooltip' not in vars(field_info):
            tooltip = field_info.description
    return hint, tooltip


def reserves_bottom_space(field_info: FieldInfo, description_as: DescriptionTarget = DESCRIPTION_AS) -> bool:
    """
    Whether this field is taller than its box: Quasar keeps a strip of 20px free below a field
    that *can* show a message, so that the layout does not jump when one appears
    (`q-field--with-bottom`).

    Two things ask for that strip, and both are niceview's own doing: a validation — NiceGUI
    reserves the space for it (`error=False`), and ModelForm wires one on every VALIDATED_WIDGET
    — and a hint, on the QInput based widgets that have a slot for one. Everything else, a
    switch or a slider or a group of checkboxes, is exactly as tall as it looks.

    Independent of `outlined`, `filled` and friends: those change how tall the box is, not what
    sits below it.
    """
    widget_type = field_info.widget_type or ''
    if widget_type in VALIDATED_WIDGETS:
        return True
    hint, _ = resolve_help_texts(field_info, description_as)
    return bool(hint) and widget_type in HINT_WIDGETS


def apply_field_info(widget: Any, field_info: FieldInfo, description_as: DescriptionTarget = DESCRIPTION_AS) -> None:
    """
    Apply disable, hint, tooltip, classes, style, props and validation from field_info to a
    widget. Every step is guarded by hasattr, so this works for the composite widgets
    (CheckboxGroup) as well: they forward the styling calls they support and simply miss the
    rest — a hint or a validation message has nowhere to go on a group of checkboxes.
    """
    hint, tooltip = resolve_help_texts(field_info, description_as)
    if hint:
        if field_info.widget_type in HINT_WIDGETS:
            # Set the prop directly instead of going through props('hint="..."'): the string
            # form is parsed, so a quote inside the text would inject other props — and hints
            # may come from model descriptions, which in a schema-driven form are not ours to trust.
            widget._props['hint'] = hint
        else:
            log.debug(f"widget_type '{field_info.widget_type}' has no hint slot, dropping hint {hint!r}")
    if not field_info.editable and hasattr(widget, 'disable') and callable(widget.disable):
        widget.disable()
    if tooltip and hasattr(widget, 'tooltip') and callable(widget.tooltip):
        widget.tooltip(tooltip)
    if field_info.classes and hasattr(widget, 'classes') and callable(widget.classes):
        widget.classes(field_info.classes)
    if field_info.style and hasattr(widget, 'style') and callable(widget.style):
        widget.style(field_info.style)
    if field_info.props and hasattr(widget, 'props') and callable(widget.props):
        widget.props(field_info.props)
    # Only ValidationElements have a .validation attribute; on the others (checkbox, switch,
    # slider, ...) there is nowhere to show a message. ModelForm overwrites this afterwards
    # for the fields it validates against the model.
    if field_info.validation is not None and hasattr(widget, 'validation'):
        widget.validation = field_info.validation


def create_widget(field_info: FieldInfo, name: str, push_value: Callable[[Any], None],
                  required_marker: 'str | None | _FromChromeText' = FROM_CHROME_TEXT,
                  description_as: DescriptionTarget = DESCRIPTION_AS) -> Any:
    """
    Create the widget for field_info.widget_type in the current NiceGUI context and apply
    field_info's styling. `push_value(widget)` is called to set the widget's value — right
    after creation, and again whenever late-arriving async options replace the option set.

    `name` is only used for error messages and the background task name.
    Callers wire event handlers afterwards, so that setting the initial value does not fire
    a change event. 'editgrid' and 'modelselect' must be handled by the caller ('modelselect'
    is rendered as a select once its options have been resolved from the repository).
    """
    widget_type = field_info.widget_type
    if isinstance(required_marker, _FromChromeText):
        required_marker = text_of(get_chrome_text().required_marker)
    label = _label(field_info, required_marker)
    widget: Any = None

    if widget_type == 'ui.input':
        widget = ui.input(label=label, **_pick_attrs(field_info, ['placeholder', 'password', 'password_toggle_button', 'autocomplete', 'prefix', 'suffix']))
        push_value(widget)

    elif widget_type == 'ui.number':
        widget = ui.number(label=label, **_pick_attrs(field_info, ['placeholder', 'min', 'max', 'precision', 'step', 'prefix', 'suffix', 'number_format'], rename={'number_format': 'format'}))
        push_value(widget)

    elif widget_type == 'ui.textarea':
        widget = ui.textarea(label=label, **_pick_attrs(field_info, ['placeholder']))
        push_value(widget)

    elif widget_type == 'ui.checkbox':
        widget = ui.checkbox(text=label)
        push_value(widget)

    elif widget_type == 'ui.switch':
        widget = ui.switch(text=label)
        push_value(widget)

    elif widget_type in ('ui.select', 'modelselect'):
        widget = _create_select_widget(field_info, name, push_value, label)

    elif widget_type == 'ui.radio':
        widget = _create_choice_widget(ui.radio, field_info, name, push_value, required_marker)

    elif widget_type == 'ui.toggle':
        widget = _create_choice_widget(ui.toggle, field_info, name, push_value, required_marker)

    elif widget_type == 'checkbox_group':
        widget = _create_checkbox_group_widget(field_info, name, push_value, required_marker)
        # 'inline' is a niceview layout directive consumed above, not a Quasar prop: keep it
        # from reaching the container as an HTML attribute.
        field_info = _without_prop(field_info, 'inline')

    elif widget_type == 'ui.color_input':
        widget = ui.color_input(label=label, **_pick_attrs(field_info, ['placeholder']), preview=field_info.color_preview)
        push_value(widget)

    elif widget_type == 'ui.input_chips':
        widget = ui.input_chips(label=label, **_pick_attrs(field_info, ['new_value_mode', 'clearable']))
        push_value(widget)

    elif widget_type == 'datetime':
        widget = ui.input(label=label, **_pick_attrs(field_info, ['placeholder'])).props('type=datetime-local').props('step=1')
        push_value(widget)

    elif widget_type == 'date':
        # Prefer the native HTML date input over NiceGUI/Quasar's date_input because it is
        # more lightweight and has better browser support. Value format is YYYY-MM-DD.
        widget = ui.input(label=label, **_pick_attrs(field_info, ['placeholder'])).props('type=date')
        push_value(widget)

    elif widget_type == 'time':
        # Same rationale as 'date': prefer the native HTML time input over NiceGUI/Quasar.
        widget = ui.input(label=label, **_pick_attrs(field_info, ['placeholder'])).props('type=time').props('step=1')
        push_value(widget)

    elif widget_type == 'timedelta':
        widget = ui.input(label=label, **_pick_attrs(field_info, ['placeholder']))
        push_value(widget)

    elif widget_type == 'ui.slider':
        slider_min = field_info.min if field_info.min is not None else 0.0
        slider_max = field_info.max if field_info.max is not None else 100.0
        slider_kwargs: dict[str, Any] = {'min': slider_min, 'max': slider_max}
        if field_info.step is not None:
            slider_kwargs['step'] = field_info.step
        with _labelled(field_info, required_marker, 'w-full gap-1'):
            widget = ui.slider(**slider_kwargs).props('label-always')
        push_value(widget)

    elif widget_type == 'ui.rating':
        rating_max = int(field_info.max) if field_info.max is not None else 5
        with _labelled(field_info, required_marker):
            widget = ui.rating(max=rating_max)
        push_value(widget)

    if widget is None:
        raise ValueError(f"Invalid widget class: {widget_type}")

    if field_info.clearable and widget_type in CLEARABLE_PROP_WIDGETS:
        widget.props('clearable')

    apply_field_info(widget, field_info, description_as)
    return widget


def _without_prop(field_info: FieldInfo, prop: str) -> FieldInfo:
    """A copy of field_info with one whitespace-separated token removed from its props."""
    if not field_info.props:
        return field_info
    return _merge_field_infos(field_info, FieldInfo(props=' '.join(p for p in field_info.props.split() if p != prop)))


def _create_select_widget(field_info: FieldInfo, name: str, push_value: Callable[[Any], None], label: str) -> ui.select:
    """Create a select widget. Options come from options/literal_options on field_info."""
    kwargs = _pick_attrs(field_info, ['with_input', 'multiple', 'clearable', 'new_value_mode', 'key_generator'])
    kwargs['options'], pending = _resolve_options(name, field_info)
    widget = ui.select(label=label, **kwargs)
    push_value(widget)
    if pending is not None:
        _schedule_late_options(name, pending, _make_late_options_applier(widget, push_value))
    return widget


def _create_choice_widget(element: Callable[..., Any], field_info: FieldInfo, name: str,
                          push_value: Callable[[Any], None], required_marker: str | None) -> Any:
    """Create a radio or toggle widget. Options come from options/literal_options on field_info."""
    options, pending = _resolve_options(name, field_info)
    kwargs = _pick_attrs(field_info, ['clearable']) if element is ui.toggle else {}
    with _labelled(field_info, required_marker):
        widget = element(options, **kwargs)
    push_value(widget)
    if pending is not None:
        _schedule_late_options(name, pending, _make_late_options_applier(widget, push_value))
    return widget


def _create_checkbox_group_widget(field_info: FieldInfo, name: str, push_value: Callable[[Any], None],
                                  required_marker: str | None) -> CheckboxGroup:
    """
    Create a row/column of ui.checkbox elements for a list[Literal[...]] field.
    Options come from options/literal_options on field_info.
    Layout is vertical by default; pass props='inline' (same convention as ui.radio) for a
    horizontal row.
    """
    raw_options, pending = _resolve_options(name, field_info)
    items = list(raw_options.items()) if isinstance(raw_options, dict) else [(opt, opt) for opt in raw_options]

    inline = field_info.props is not None and 'inline' in field_info.props.split()
    container = ui.row if inline else ui.column

    checkboxes: dict[Any, ui.checkbox] = {}
    with _labelled(field_info, required_marker):
        with container().classes(get_field_style().checkbox_group_classes) as container_element:
            for opt, label in items:
                checkboxes[opt] = ui.checkbox(text=str(label))

    widget = CheckboxGroup(list(checkboxes.keys()), checkboxes, container_element)
    push_value(widget)
    if pending is not None:
        _schedule_late_options(name, pending, _make_late_options_applier(widget, push_value))
    return widget


# --- public model-free entry point -----------------------------------------

def render_field(field_info: FieldInfo, value: Any = None, *, local_tz: str | None = None,
                 required_marker: 'str | None | _FromChromeText' = FROM_CHROME_TEXT,
                 description_as: DescriptionTarget = DESCRIPTION_AS) -> Any:
    """
    Render a single widget from a FieldInfo in the current NiceGUI context, initialised to
    `value`, and return it.

    The widget-building half of ModelForm without the model: no Fields, no item, no adapter,
    no autosave, no change events — the caller reads the widget itself, via
    `field_value(widget, field_info)` for the same value conversions ModelForm applies.

    ```python
    fi = niceview.Field(label='Name', widget_type='ui.input', props='outlined dense', classes='w-full')
    widget = niceview.render_field(fi, 'Alice')
    ...
    name = niceview.field_value(widget, fi)
    ```

    `field_info.widget_type` is required — without a model there is nothing to infer it from.
    label / placeholder / hint / tooltip / props / classes / style / options and the
    widget-specific attributes (min, max, step, multiple, ...) are applied exactly as in a
    ModelForm, and so is validation: `required` rejects an empty value, then
    `field_info.validation` runs as NiceGUI's own validation would. What a ModelForm adds on
    top — validating the whole item against a Pydantic model — is the only difference.

    `required` also appends `required_marker` to the label — ChromeText's by default; pass
    `required_marker=None` for none.

    `field_info.description` is help text without a fixed place: `description_as` decides
    whether it is rendered as the hint, as the tooltip, or not at all. It is the slot for text
    that came from a schema rather than from the person laying out the form — an explicit
    `hint` or `tooltip` on the FieldInfo always wins over it.

    Raises ValueError if widget_type is missing, unknown, or one of 'editgrid' / 'modelselect'
    (both need a model type and a repository — use ModelForm for those).
    """
    if not isinstance(field_info, FieldInfo):
        raise TypeError(f"field_info must be a FieldInfo, got {type(field_info)}")
    widget_type = field_info.widget_type
    if not widget_type:
        raise ValueError("render_field() requires field_info.widget_type to be set: without a model there is no type to infer it from")
    if widget_type in MODEL_ONLY_WIDGETS:
        raise ValueError(f"render_field() does not support widget_type '{widget_type}': it needs a model type and a repository (use ModelForm)")

    def push_value(widget: Any) -> None:
        widget.value = to_widget_value(field_info, value, local_tz=local_tz)

    widget = create_widget(field_info, field_info.label or widget_type, push_value, required_marker, description_as)
    if field_info.required and hasattr(widget, 'validation'):
        # Chain the required check in front of the caller's own validation, same order as
        # ModelForm's — apply_field_info() has already set field_info.validation.
        own = field_info.validation

        def validate(value: Any, own: Any = own) -> Any:
            return required_error(field_info, value) or run_validation(own, value)

        widget.validation = validate
        widget.validate(return_result=False)
    return widget
