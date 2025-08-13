from copy import copy
from dataclasses import dataclass
import datetime
from typing import Any, Callable, Iterable, List, Literal, Self, TypeVar, Unpack
import typing_extensions
from pydantic import BaseModel
from nicegui import ui
from nicegui.events import Handler, ClickEventArguments, ValueChangeEventArguments, handle_event
from nicegui.dataclasses import KWONLY_SLOTS

from niceview.dataadapter import ModelDataAdapter
from niceview.fieldinfo import FieldInfo
from niceview.fields import Fields


def _collect_aggrid_cols(fields: Fields) -> list[dict[str, Any]]:
    cols = []
    for name in fields:
        info = fields[name]
        if info.hidden or info.table_hidden:
            continue  # Skip hidden fields
        # Create a column for the field
        col = {
            'headerName': info.table_label or info.label,
            'field': name,
            # TODO table_align
            'sortable': info.table_sortable,
            #'type': field_info.aggrid_type or 'text',  # TODO default to 'text' if not specified
            # 'filter': 'agTextColumnFilter' or 'agNumberColumnFilter' or 'agDateColumnFilter' based on field type
            # 'floatingFilter': True
        }
        if info.table_cell_style:
            col['cellStyle'] = info.table_cell_style
        if info.table_sort:
            col['sort'] = info.table_sort
        if info.table_filterable:
            if info.field_type in [int, float]:
                col['filter'] = 'agNumberColumnFilter'
            elif info.field_type in [datetime.datetime, datetime.date, datetime.time]:
                col['filter'] = 'agDateColumnFilter'
            else:
                col['filter'] = 'agTextColumnFilter'
            if info.table_floating_filter:
                col['floatingFilter'] = True

        # add column properties (from https://www.ag-grid.com/vue-data-grid/column-properties/)
        if info.aggrid:
            col.update(info.aggrid)
        # add the column
        cols.append(col)
    
    return cols


class _ModelGridOptionInputs(typing_extensions.TypedDict, total=False):
    """
    Kwarg Options for the UiAgGrid class.
    """
    fields: list[str] | str # FieldsMixin: list of field names or '__all__' (default) to include all fields
    exclude: list[str] | str # FieldsMixin: list of field names to exclude from the grid
    field_infos: dict[str, FieldInfo] # FieldsMixin: dict of field names to FieldInfo objects to override the info from the model

    classes: str
    tailwind: str
    style: str
    props: str
    theme: str
    auto_size_columns: bool
    defaultColDef: dict
    rowSelection: Literal[None, 'single', 'multiple']
    cell_renderers: dict[str, Callable[[Any], str]]


T = TypeVar('T', bound=BaseModel)
class ModelGrid:
    """
    A AgGrid class that can be used to create tables for Pydantic models.
    """
    #_items: Iterable
    _fields: Fields
    _data: ModelDataAdapter
    _selection_handlers: List[Handler[ValueChangeEventArguments]]
    _cols: list[dict[str, str]]
    _rows: list[dict[str, Any]]

    widget: ui.aggrid | None = None
    classes: str
    tailwind: str
    style: str
    props: str
    theme: str
    auto_size_columns: bool | None
    defaultColDef: dict
    rowSelection: Literal[None, 'single', 'multiple'] = None
    cell_renderers: dict[str, Callable[[Any], Any]]


    def __init__(self, item_type: type[T], data: ModelDataAdapter, **kwargs: Unpack[_ModelGridOptionInputs]) -> None:
        """
        Initialize the ModelGrid with a Pydantic model type and a list of items.
        The items must be instances of the model type.

        Note: item_type is needed to determine the type of the items in the grid in case of empty items.
        """
        # check parameter types
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"cls must be a subclass of BaseModel, got {type(item_type)}")
        self._fields = Fields(item_type, kwargs.pop('fields', '__all__'),
                            kwargs.pop('exclude', ''), kwargs.pop('field_infos', {}))
        self._data = data

        # initialize instance with a new copy of more complex data structures
        self._selection_handlers = []
        self.widget = None
        self.classes = kwargs.pop('classes', '')
        self.tailwind = kwargs.pop('tailwind', '')
        self.style = kwargs.pop('style', '')
        self.props = kwargs.pop('props', '')
        self.theme = kwargs.pop('theme', '')
        self.auto_size_columns = kwargs.pop('auto_size_columns', None)
        self.defaultColDef = copy(kwargs.pop('defaultColDef', {}))
        self.rowSelection = kwargs.pop('rowSelection', None)
        self.cell_renderers = copy(kwargs.pop('cell_renderers', {}))


    def on_select(self, callback: Handler[ValueChangeEventArguments]) -> Self:
        """
        Add a callback to be invoked when the selection changes.
        The callback will receive a ValueChangeEventArguments with the new selection.
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._selection_handlers.append(callback)
        return self


    def update_rows(self) -> Self:
        """
        Re-Render the rows of the table.
        """
        self._rows.clear() # modify the rows in place without creating a new list
        for i, item in enumerate(self._data):
            row = {'__ui_row_key': self._data.key_from_item(item, i)}
            for field_name in self._fields:
                field_info = self._fields[field_name]
                if field_info.hidden or field_info.table_hidden:
                    # Skip hidden fields
                    continue
                value = getattr(item, field_name)
                if field_name in self.cell_renderers:
                    row[field_name] = self.cell_renderers[field_name](value)
                elif isinstance(value, list):
                    # If the value is a list, we can render it as a comma-separated string
                    row[field_name] = ', '.join(str(v) for v in value)
                elif isinstance(value, BaseModel):
                    # If the value is a BaseModel, we can use its string representation
                    row[field_name] = str(value)
                else:
                    row[field_name] = value
            self._rows.append(row)
        if self.widget:
            self.widget.update()
        return self


    def render(self) -> Self:
        """
        Render the table. If the model is given, it will be bound to the grid.
        """
        self._cols = _collect_aggrid_cols(self._fields)
        self._rows = []
        self.update_rows()

        kwargs = { k: v for k in ['theme', 'auto_size_columns']
                   if ( v := getattr(self, k)) }
        config_dict = { 'columnDefs': self._cols, 'rowData': self._rows, 'stopEditingWhenCellsLoseFocus': True, }
        if self.defaultColDef:
            config_dict['defaultColDef'] = self.defaultColDef
        if self.rowSelection:
            config_dict['rowSelection'] = self.rowSelection

        self.widget = ui.aggrid(config_dict, **kwargs)
        self.widget.classes(self.classes)
        self.widget.tailwind(self.tailwind)
        self.widget.style(self.style)
        self.widget.props(self.props)
        self.widget.on('selectionChanged', self._handle_selection_changed)

        return self


    async def _handle_selection_changed(self, event) -> None:
        """
        Handle the row selected event to call the selection handlers.
        """
        row = await self.widget.get_selected_row()
        # print(f"rowSelected: {event} {row}")
        # rowSelected: GenericEventArguments(sender=<nicegui.elements.aggrid.AgGrid object at 0x1123c1090>, client=<nicegui.client.Client object at 0x1123c02d0>, args={'source': 'rowClicked'}) {'__ui_row_key': 1, 'name': 'Jane Doe', 'age': 25, 'num': 43, 'is_active': True, 'is_admin': True, 'birthdatetime': '2025-06-10T10:19:47+00:00', 'gender': 'other'}
        e = ValueChangeEventArguments(sender=event.sender, client=event.client, value=row)
        for handler in self._selection_handlers:
            handle_event(handler, e)


@dataclass(**KWONLY_SLOTS)
class TableItemEventArguments(ClickEventArguments):
    model_table: ModelGrid
    row_key: str
    item: Any


@dataclass(**KWONLY_SLOTS)
class TableItemFieldEventArguments(TableItemEventArguments):
    field_name: str
    new_value: Any


class _InlineEditableModelGridOptionInputs(_ModelGridOptionInputs, total=False):
    cell_readers: dict[str, Callable[[str], Any]]


class ModelGridInlineEdit(ModelGrid):
    """
    A grid class that can be used to create inline-editable aggrids for Pydantic models.
    """
    _change_handlers: List[Handler[TableItemFieldEventArguments]]
    _delete_handler: Callable[[Iterable, int], bool] | None
    _edit_create_handler: Callable[[Iterable, int], bool] | None

    cell_readers: dict[str, Callable[[str], Any]]

    def __init__(self, item_type: type[T], data: ModelDataAdapter, **kwargs: Unpack[_InlineEditableModelGridOptionInputs]) -> None:
        self.cell_readers = kwargs.pop('cell_readers', {})

        super().__init__(item_type, data, **kwargs)
        self.defaultColDef.update({'editable': True})

        self._change_handlers = []
        self._delete_handler = None
        self._edit_create_handler = None


    def on_change(self, callback: Handler[TableItemFieldEventArguments]) -> Self:
        """
        Add a callback to be invoked when the form values change after successful validation. 
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._change_handlers.append(callback)
        return self


    def render(self) -> Self:
        """
        Render the grid with inline editing capabilities.
        """
        super().render()

        # add the cell value changed handler
        if self.widget:
            self.widget.on('cellValueChanged', self._handle_cell_value_changed)

        return self


    def _handle_cell_value_changed(self, event) -> None:
        """
        Handle the cell value changed event to update the model with the new value
        when using inline editing (aggrid_editable).
        """
        # print(f"cellValueChanged: {event}")
        # GenericEventArguments(sender=<nicegui.elements.aggrid.AgGrid object at ...>, client=<nicegui.client.Client object at ...>,
        #  args={'value': 'John Doexfdsdf', 'oldValue': 'John Doe', 'newValue': 'John Doexfdsdf', 'rowIndex': 0, 
        #   'data': {'__ui_row_key': 0, 'name': 'John Doexfdsdf', 'age': 30}, 
        #   'source': 'edit', 'colId': 'name', 'selected': True, 'rowHeight': 28, 'rowId': '0'})
        row_index = event.args['rowIndex']
        # row_id = event.args['rowId']
        row_key = event.args['data']['__ui_row_key']
        field_name = event.args['colId']
        old_value = event.args['oldValue']
        new_value = event.args['newValue']

        if field_name in self.cell_readers:
            old_value = self.cell_readers[field_name](old_value)
            new_value = self.cell_readers[field_name](new_value)

        #  validate the model with the new value
        errors = []
        item = None
        try:
            item = self._data.read(row_key)
            dumped_item = item.model_dump()
            dumped_item[field_name] = new_value
            errors = self._fields.validation_error_list(dumped_item)
        except Exception as e:
            errors.append(f"Internal error: Row {row_index}/{row_key} not found - try again")
        if not isinstance(item, self._fields._item_type):
            raise TypeError(f"model must be an instance of {self._fields._item_type}, got {type(item)}")
        if not hasattr(item, field_name):
            raise ValueError(f"Field {field_name} not found in model {item}")

        # update the model with the new value
        if len(errors) == 0:
            setattr(item, field_name, new_value)
            self._data.update(item, row_key)
        else:
            # if there are validation errors, revert the value to the old value
            ui.notify(f"Invalid input {new_value}: {errors}", color='negative')
            self.update_rows()

        # call the change handlers
        tife = TableItemFieldEventArguments(
            sender=event.sender, client=event.client, 
            model_table=self,  # type:ignore[arg-type]  # self is a ModelGridInlineEdit
            row_key=row_key,
            item=item, field_name=field_name, new_value=new_value,
        )
        for handler in self._change_handlers:
            handle_event(handler, tife)
