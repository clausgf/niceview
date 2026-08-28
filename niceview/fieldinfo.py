from typing import Any, Awaitable, Callable, Literal, TypeAlias, Unpack
import typing_extensions

from nicegui.elements.mixins.validation_element import ValidationFunction, ValidationDict


WidgetType = Literal[
    'ui.input', 'ui.number', 'ui.textarea', 'ui.checkbox', 'ui.switch', 'ui.select', 'ui.radio', 'ui.toggle', 'ui.color_input', 'ui.input_chips',
    'ui.slider', 'ui.rating',
    'checkbox_group',
    'datetime', 'date', 'time', 'timedelta',
    'editgrid', 'modelselect',
]
"""All widget types a field can be rendered as. 'ui.*' widgets map directly to a native NiceGUI
element of the same name; unprefixed widgets (checkbox_group, datetime, date, time, timedelta,
editgrid, modelselect) are niceview-specific (composite widgets or ui.input variants)."""


OptionsSource: TypeAlias = list | dict | Callable[[], list | dict | Awaitable[list] | Awaitable[dict]]
"""Source of choices for select/radio/toggle/checkbox_group widgets: a list, a dict
(value -> label), or a zero-argument callable returning either — the callable may be
sync or async (an async callable's options are applied as soon as they are available)."""


class _FieldInfoInputs(typing_extensions.TypedDict, total=False):
    """Keyword options for FieldInfo(); mirrors its attributes for kwarg type-checking."""
    label: str
    """The field's label text."""
    placeholder: str
    """Placeholder text shown in an empty text-like widget."""

    field_type: type
    """Python type of the value. ModelForm sets this from the model annotation; set it
    explicitly for render_field()."""

    required: bool
    """Whether the field must have a value."""
    hidden: bool
    """Hide the field entirely."""
    editable: bool
    """Whether the widget accepts input; False renders it disabled."""
    hint: str
    """Help text below the widget (Quasar's `hint` prop); ignored by widgets with no hint slot."""
    description: str
    """Help text from pydantic's `description`; shown as hint or tooltip per `description_as=`,
    unless an explicit `hint`/`tooltip` wins."""
    widget_type: WidgetType
    """Which element renders the field; inferred from the type if omitted."""

    props: str
    """Quasar props string, merged on top of niceview's own."""
    classes: str
    """CSS classes for the widget."""
    style: str
    """Inline CSS style for the widget."""
    tooltip: str
    """Text shown on hover."""

    # choices for select/radio/toggle/checkbox_group widgets
    options: OptionsSource
    """Choices for select/radio/toggle/checkbox_group widgets."""

    # additional options when field is rendered in a ui.input widget
    password: bool
    """Mask the input (ui.input only)."""
    password_toggle_button: bool
    """Show/hide toggle for a password input."""
    autocomplete: list[str]
    """Autocomplete suggestions for a text input."""
    validation: ValidationFunction | ValidationDict
    """Extra validation beyond `required`: a NiceGUI ValidationFunction or dict."""

    # additional options when field is rendered as ui.number
    min: float
    """Minimum value (ui.number)."""
    max: float
    """Maximum value (ui.number)."""
    precision: int
    """Decimal places (ui.number)."""
    step: float
    """Increment step (ui.number)."""
    prefix: str
    """Text shown before the value (ui.number)."""
    suffix: str
    """Text shown after the value (ui.number)."""
    number_format: str
    """Display format of ui.number, e.g. '%.2f'. Named number_format, not format, to keep it
    apart from JSON Schema's `format`, which corresponds to widget_type."""

    # a clear button, on the select-like widgets and on every text input
    clearable: bool
    """Offer a clear button on select-like and text widgets. Clearing writes None."""

    # additional options when field is rendered as ui.select
    with_input: bool
    """Allow free-text filtering in ui.select."""
    multiple: bool
    """Allow selecting multiple values in ui.select."""
    key_generator: Callable[[Any], Any]
    """Generates a dict key for a new value typed into ui.select."""
    # validation same as in ui.input

    # additional options when field is rendered as ui.color_input
    color_preview: bool
    """Show a color swatch preview next to ui.color_input."""

    # additional options when the field is rendered as ui.input_chips
    new_value_mode: Literal['add', 'add-unique', 'toggle']
    """How ui.input_chips treats a typed value not already in the list."""

    # item type for list fields (editgrid) and relationship fields (modelselect)
    item_type: type
    """Item's pydantic type for editgrid/modelselect fields."""

    # options when field is used in a table or grid column
    table_label: str
    """Column header label; defaults to the field's label."""
    table_hidden: bool
    """Hide the column in a table/grid (the field may still show in a form)."""
    table_align: Literal['left', 'center', 'right']
    """Horizontal text alignment of the cell."""
    table_cell_style: str
    """Extra CSS for the cell, merged with table_align."""
    table_sortable: bool
    """Whether the column can be sorted."""
    table_sort: Literal['asc', 'desc']
    """Default sort order for the column."""
    table_filterable: bool
    """Show a filter row for the column; filter type inferred from the field type."""
    table_floating_filter: bool
    """Show a floating filter row for the column."""
    aggrid_type: str
    """ag-grid column type, e.g. 'numericColumn', 'rightAligned'."""
    aggrid: dict
    """Additional ag-grid column properties, merged on top of the computed ones."""


class FieldInfo():
    """
    Per-field UI metadata, the rendering counterpart of pydantic's Field: not validation or
    serialization, but how a field looks and behaves in forms and tables.
    """
    field_type: type = str
    """Python type of the value. Resolved from the model annotation by Fields; set it explicitly
    when building a FieldInfo by hand for render_field()."""

    label: str = ''
    """The field's label text."""
    placeholder: str | None = None
    """Placeholder text shown in an empty text-like widget."""

    required: bool | None = None
    """Whether the field must have a value. None until Fields resolves it from pydantic's
    is_required() — a different concept from pydantic's own required."""
    hidden: bool = False
    """Hide the field entirely."""
    editable: bool = True
    """Whether the widget accepts input; False renders it disabled."""
    hint: str | None = None
    """Help text shown below the widget (Quasar's `hint` prop). Set explicitly; widgets without
    a hint slot (see widgets.HINT_WIDGETS) ignore it."""
    description: str | None = None
    """What the model says the field means, resolved from pydantic's `description`. Carried as
    metadata only — `description_as` decides at render time whether it becomes the hint, the
    tooltip, or nothing at all, and an explicit `hint`/`tooltip` always wins over it."""
    widget_type: WidgetType | None = None
    """Which element renders the field; inferred from the type if omitted."""

    props: str | None = None
    """Quasar props string, merged on top of niceview's own."""
    classes: str | None = None
    """CSS classes for the widget."""
    style: str | None = None
    """Inline CSS style for the widget."""
    tooltip: str | None = None
    """Text shown on hover."""

    aggrid: dict[str, str] | None = None
    """Additional ag-grid column properties, e.g. {'headerName': 'My Column'}, merged on top of
    the computed ones."""

    options: OptionsSource | None = None
    """Choices for select/radio/toggle/checkbox_group widgets. Resolution order per widget:
    options, then literal_options (auto-extracted from Literal[...] types). checkbox_group lays
    out horizontally via props='inline' (same convention as ui.radio)."""

    # additional options when field is rendered in a ui.input widget
    password: bool = False
    """Mask the input (ui.input only)."""
    password_toggle_button: bool = False
    """Show/hide toggle for a password input."""
    autocomplete: list[str] | None = None
    """Autocomplete suggestions for a text input."""
    validation: ValidationFunction | ValidationDict | None = None
    """Extra validation beyond `required`: a NiceGUI ValidationFunction or dict."""

    # additional options when field is rendered as ui.number
    min: float | None = None
    """Minimum value (ui.number)."""
    max: float | None = None
    """Maximum value (ui.number)."""
    precision: int | None = None
    """Decimal places (ui.number)."""
    step: float | None = None
    """Increment step (ui.number)."""
    prefix: str | None = None
    """Text shown before the value (ui.number)."""
    suffix: str | None = None
    """Text shown after the value (ui.number)."""
    number_format: str | None = None
    """Display format of ui.number, e.g. '%.2f'. Named number_format, not format, to keep it
    apart from JSON Schema's `format`, which corresponds to widget_type."""

    clearable: bool = False
    """Offer a clear button. Honoured by the select-like widgets and by every text input,
    ui.color_input included; a widget without a clear affordance (checkbox, switch, radio,
    slider, rating, checkbox_group) ignores it. Clearing writes None into the field."""

    # additional options when field is rendered as ui.select
    with_input: bool = False
    """Allow free-text filtering in ui.select."""
    multiple: bool = False
    """Allow selecting multiple values in ui.select."""
    key_generator: Callable[[Any], Any] | None = None
    """Generates a dict key for a new value typed into ui.select."""

    # additional options when field is rendered as ui.color_input
    color_preview: bool = False
    """Show a color swatch preview next to ui.color_input."""

    # options inferred from Literal type args — set by Fields, not user-settable
    literal_options: list | None = None
    """Choices auto-extracted from a Literal[...] annotation; set by Fields, not user-settable."""

    # additional options when the field is rendered as ui.input_chips
    new_value_mode: Literal['add', 'add-unique', 'toggle'] = 'add-unique'
    """How ui.input_chips treats a typed value not already in the list."""

    # additional options when field is a relationship field
    item_type: type | None = None
    """Item's pydantic type for editgrid/modelselect fields."""

    # options when field is used in a table or grid column
    table_label: str = ''
    """Column header label; defaults to the field's label."""
    table_hidden: bool = False
    """Hide the column in a table/grid (the field may still show in a form)."""
    table_align: Literal['left', 'center', 'right'] | None = None
    """Horizontal text alignment of the cell."""
    table_cell_style: str = ''
    """Extra CSS for the cell, merged with table_align."""
    table_sortable: bool = True
    """Whether the column can be sorted."""
    table_sort: Literal[None, 'asc', 'desc'] | None = None
    """Default sort order for the column."""
    table_filterable: bool = True
    """Show a filter row for the column; filter type inferred from the field type."""
    table_floating_filter: bool = False
    """Show a floating filter row for the column."""
    aggrid_type: str | None = None
    """ag-grid column type, e.g. 'numericColumn', 'rightAligned'."""


    def __init__(self, **kwargs: Unpack[_FieldInfoInputs]):
        # Initialize the field with the provided keyword arguments.
        for key, value in kwargs.items():
            if hasattr(self, key):
                # use default value if not provided (not None)
                if value is not None:
                    setattr(self, key, value)
            else:
                raise TypeError(f"Unexpected keyword argument for FieldInfo: {key}")

    def __repr__(self):
        """Print non-none values"""
        non_default_values = {k: v for k, v in self.__dict__.items() if v is not None}
        formatted_values = ', '.join(
            f"{k}={v!r}"
            for k, v in non_default_values.items()
        )
        if formatted_values:
            return f"{self.__class__.__name__}({formatted_values})"
        return super().__repr__()


_FIELD_INFO_KWARGS = set(_FieldInfoInputs.__annotations__.keys())


def _merge_field_infos(base: FieldInfo, override: FieldInfo) -> FieldInfo:
    """Return a new FieldInfo with base values overridden by explicitly set values from override."""
    merged = FieldInfo()
    merged.__dict__.update(base.__dict__)  # copy all instance attrs incl. field_type, literal_options, etc.
    for k, v in vars(override).items():
        if k in _FIELD_INFO_KWARGS:
            setattr(merged, k, v)
    return merged
