import datetime
from typing import Any, Awaitable, Callable, Dict, List, Literal, Union, Unpack
import typing
from pydantic import BaseModel
import pydantic
import typing_extensions

from nicegui import ui
from nicegui.elements.mixins.validation_element import ValidationFunction, ValidationDict


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
    widget_type: Literal['ui.input', 'ui.number', 'datetime', 'date', 'time', 'ui.textarea', 'ui.checkbox', 'ui.switch', 'ui.select', 'editgrid', 'modelselect']

    props: str
    classes: str
    tailwind: str
    style: str
    tooltip: str

    # additional options when field is renderd in a ui.input widget
    password: bool
    password_toggle_button: bool
    autocomplete: List[str]
    validation: Union[ValidationFunction, ValidationDict]

    # addtional options when field is rendered as ui.number
    min: float
    max: float
    precision: int
    step: float
    prefix: str
    suffix: str
    format: str

    # additional options when field is rendered as ui.select
    select_options: Union[List, Dict, Callable[[], list]]
    with_input: bool
    multiple: bool
    clearable: bool
    # validation same as in ui.input

    # additional options when field is rendered as onetomany
    o2m_item_type: type  # type of the item in the one-to-many relationship, e.g. Group

    # options when field is used in a table or grid column
    table_label: str  # label for the table column, if not set, the field label is used
    table_hidden: bool
    table_cell_style: str  # CSS style for the cell, e.g. 'text-align: center;'
    table_sortable: bool
    table_sort: Literal['asc', 'desc'] # default sorting order
    table_filterable: bool  # whether to show a filter row in the table; if applicable, filter type is inferred from the field type
    table_floating_filter: bool  # whether to show a floating filter row in the table


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

    required: bool = False  # this is not the same as required in pydantic
    hidden: bool = False
    editable: bool = True
    help_text: str | None = None
    # widget type for the field  (default infered from field type)
    widget_type: Literal['ui.input', 'ui.number', 'datetime', 'date', 'time', 'ui.textarea', 'ui.checkbox', 'ui.switch', 'ui.select', 'editgrid'] | None = None

    # ui.element
    props: str | None = None
    classes: str | None = None
    tailwind: str | None = None
    style: str | None = None
    tooltip: str | None = None

    # options when field is rendered as ui.aggrid column
    aggrid: dict[str, str] | None = None  # additional options for the aggrid column, e.g. {'headerName': 'My Column', 'field': 'my_field'}

    # additional options when field is renderd in a ui.input widget
    password: bool = False
    password_toggle_button: bool = False
    autocomplete: List[str] | None = None
    validation: Union[None, ValidationFunction, ValidationDict] = None

    # addtional options when field is rendered as ui.number
    min: float | None = None
    max: float | None = None
    precision: int | None = None
    step: float | None = None
    prefix: str | None = None
    suffix: str | None = None
    format: str | None = None

    # additional options when field is rendered as ui.select
    select_options: Union[None, List, Dict, Callable[[], Awaitable[list[str]]]] = None  # list of options for the select widget
    with_input: bool = False
    multiple: bool = False
    clearable: bool = False

    # additional options when field is a relationship field
    item_type: type | None = None

    # options when field is used in a table or grid column
    table_label: str = ''
    table_hidden: bool = False
    table_cell_style: str = ''
    table_sortable: bool = True
    table_sort: Literal[None, 'asc', 'dsc'] | None = None
    table_filterable: bool = True
    table_floating_filter: bool = False


    def __init__(self, **kwargs: Unpack[_FieldInfoInputs]):
        # Initialize the field with the provided keyword arguments.
        for key, value in kwargs.items():
            if hasattr(self, key):
                # use default value if not provided (not None)
                if value is not None:
                    setattr(self, key, value)
            else:
                raise ValueError(f"Invalid field name: {key}")

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


