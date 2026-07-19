from typing import Awaitable, Callable, Literal, TypeAlias, Unpack
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
    """
    This class exists solely to add type checking for `**kwargs` (idea from pydantic class _FromFieldInfoInputs)
    """
    label: str
    placeholder: str

    required: bool
    hidden: bool
    editable: bool
    help_text: str
    widget_type: WidgetType

    props: str
    classes: str
    style: str
    tooltip: str

    # choices for select/radio/toggle/checkbox_group widgets
    options: OptionsSource

    # additional options when field is rendered in a ui.input widget
    password: bool
    password_toggle_button: bool
    autocomplete: list[str]
    validation: ValidationFunction | ValidationDict

    # additional options when field is rendered as ui.number
    min: float
    max: float
    precision: int
    step: float
    prefix: str
    suffix: str
    format: str

    # additional options when field is rendered as ui.select
    with_input: bool
    multiple: bool
    clearable: bool
    # validation same as in ui.input

    # additional options when field is rendered as ui.color_input
    color_preview: bool

    # additional options when the field is rendered as ui.input_chips
    new_value_mode: Literal['add', 'add-unique', 'toggle']

    # item type for list fields (editgrid) and relationship fields (modelselect)
    item_type: type

    # options when field is used in a table or grid column
    table_label: str  # label for the table column, if not set, the field label is used
    table_hidden: bool
    table_align: Literal['left', 'center', 'right']  # horizontal text alignment in the cell
    table_cell_style: str  # additional CSS style for the cell (merged with table_align)
    table_sortable: bool
    table_sort: Literal['asc', 'desc']  # default sorting order
    table_filterable: bool  # whether to show a filter row in the table; if applicable, filter type is inferred from the field type
    table_floating_filter: bool  # whether to show a floating filter row in the table
    aggrid_type: str  # aggrid column type, e.g. 'numericColumn', 'rightAligned'
    aggrid: dict  # additional aggrid column properties passed through verbatim (overrides computed ones)


class FieldInfo():
    """
    Metadata for a UI field. This class is used to annotate a field similar
    to Pydantic's Field class/method.
    While pydantic's Field is used to define the properties of a field
    related to data validation and JSON serialization, this class is used
    to define the properties of a field in a UI context, such as forms and
    tables.
    """
    field_type: type = str  # the type of the field, e.g. str, int, float, bool, datetime, date, time

    label: str = ''
    placeholder: str | None = None

    # None = unresolved; set from pydantic's is_required() during field resolution.
    # Note: UI-level required is not the same as required in pydantic.
    required: bool | None = None
    hidden: bool = False
    editable: bool = True
    help_text: str | None = None
    # widget type for the field (default inferred from field type)
    widget_type: WidgetType | None = None

    # ui.element
    props: str | None = None
    classes: str | None = None
    style: str | None = None
    tooltip: str | None = None

    # options when field is rendered as ui.aggrid column
    aggrid: dict[str, str] | None = None  # additional options for the aggrid column, e.g. {'headerName': 'My Column', 'field': 'my_field'}

    # choices for select/radio/toggle/checkbox_group widgets. Resolution order per
    # widget: options, then literal_options (auto-extracted from Literal[...] types).
    # For checkbox_group, horizontal layout via props='inline' (same convention as ui.radio).
    options: OptionsSource | None = None

    # additional options when field is rendered in a ui.input widget
    password: bool = False
    password_toggle_button: bool = False
    autocomplete: list[str] | None = None
    validation: ValidationFunction | ValidationDict | None = None

    # additional options when field is rendered as ui.number
    min: float | None = None
    max: float | None = None
    precision: int | None = None
    step: float | None = None
    prefix: str | None = None
    suffix: str | None = None
    format: str | None = None

    # additional options when field is rendered as ui.select
    with_input: bool = False
    multiple: bool = False
    clearable: bool = False

    # additional options when field is rendered as ui.color_input
    color_preview: bool = False

    # options inferred from Literal type args — set by Fields, not user-settable
    literal_options: list | None = None

    # additional options when the field is rendered as ui.input_chips
    new_value_mode: Literal['add', 'add-unique', 'toggle'] = 'add-unique'

    # additional options when field is a relationship field
    item_type: type | None = None

    # options when field is used in a table or grid column
    table_label: str = ''
    table_hidden: bool = False
    table_align: Literal['left', 'center', 'right'] | None = None
    table_cell_style: str = ''
    table_sortable: bool = True
    table_sort: Literal[None, 'asc', 'desc'] | None = None
    table_filterable: bool = True
    table_floating_filter: bool = False
    aggrid_type: str | None = None


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
