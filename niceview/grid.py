from dataclasses import dataclass
import datetime
import logging
from pathlib import Path
from typing import Any, Callable, Literal, Self, TypeVar, Unpack
import typing_extensions
from pydantic import BaseModel
from nicegui import ui
from nicegui.events import Handler, ClickEventArguments, ValueChangeEventArguments, handle_event

from niceview.dataadapter import CollectionAdapter, ConflictError, ListAdapter, JsonListAdapter, ReactiveAdapter
from niceview.fieldinfo import FieldInfo
from niceview.fields import Fields

log = logging.getLogger('niceview')


def _collect_aggrid_cols(fields: Fields) -> list[dict[str, Any]]:
    cols = []
    for name in fields:
        info = fields[name]
        if info.hidden or info.table_hidden:
            continue
        col: dict[str, Any] = {
            'headerName': info.table_label or info.label,
            'field': name,
            'sortable': info.table_sortable,
        }
        if info.aggrid_type:
            col['type'] = info.aggrid_type
        cell_style = info.table_cell_style or ''
        if info.table_align:
            cell_style = f'text-align: {info.table_align};' + (f' {cell_style}' if cell_style else '')
        if cell_style:
            col['cellStyle'] = cell_style
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
        # Additional column properties: https://www.ag-grid.com/vue-data-grid/column-properties/
        if info.aggrid:
            col.update(info.aggrid)
        cols.append(col)
    return cols


class _ModelGridOptionInputs(typing_extensions.TypedDict, total=False):
    """Keyword options for ModelGrid and its factory methods."""
    include: list[str] | str
    exclude: list[str] | str
    field_infos: dict[str, FieldInfo]
    profile: str | None
    """Named field layout profile from Meta.profiles (e.g. 'summary', 'detail')."""

    theme: str
    auto_size_columns: bool
    defaultColDef: dict
    rowSelection: Literal[None, 'single', 'multiple']
    cell_renderers: dict[str, Callable[[Any], str]]


T = TypeVar('T', bound=BaseModel)


class ModelGrid:
    """
    Renders a Pydantic model collection as an ag-Grid table.

    Create via factory methods:
      ModelGrid.from_list(Type, items)         — in-memory list
      ModelGrid.from_json(Type, path)          — JSON file
      ModelGrid.from_adapter(Type, adapter)    — any CollectionAdapter

    After render(), the NiceGUI ag-Grid element is available as grid.widget.
    Apply classes/style/props via grid.widget after render:
      grid.render()
      grid.widget.classes('w-full')
    Call update_rows() to refresh the displayed data from the adapter.
    """
    _fields: Fields
    _data: CollectionAdapter
    _selection_handlers: list[Handler[ValueChangeEventArguments]]
    _auto_update_registered: bool
    _rows: list[dict[str, Any]]
    widget: ui.aggrid | None
    _theme: str
    _auto_size_columns: bool | None
    _defaultColDef: dict
    _rowSelection: Literal[None, 'single', 'multiple']
    _cell_renderers: dict[str, Callable[[Any], Any]]

    def __init__(self, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_ModelGridOptionInputs]) -> None:
        """
        Create a ModelGrid for the given Pydantic model type and adapter.
        Prefer the factory methods (from_list, from_json, from_adapter) over the constructor.
        """
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {type(item_type)}")

        self._fields = Fields(item_type, kwargs.pop('include', '__all__'),
                              kwargs.pop('exclude', ''), kwargs.pop('field_infos', {}),
                              profile=kwargs.pop('profile', None))
        self._data = adapter
        self._selection_handlers = []
        self._auto_update_registered = False
        self._rows = []
        self.widget = None
        self._theme = kwargs.pop('theme', '')
        self._auto_size_columns = kwargs.pop('auto_size_columns', None)
        self._defaultColDef = kwargs.pop('defaultColDef', {}).copy()
        self._rowSelection = kwargs.pop('rowSelection', None)
        self._cell_renderers = kwargs.pop('cell_renderers', {}).copy()

    # --- factory methods ---------------------------------------------------

    @classmethod
    def from_list(cls, item_type: type[T], items: list[T], **kwargs: Unpack[_ModelGridOptionInputs]) -> Self:
        """
        Create a grid from an in-memory list.

        Pass a plain list for manual control: the grid updates only when update_rows()
        is called explicitly (e.g. via the EditGridWrapper Refresh button).

        Pass an ObservableList for automatic updates: the grid re-renders whenever
        the list is mutated structurally (append, delete, replace) without any
        explicit update_rows() call.

        Return type is Self so subclasses (e.g. ModelGridInlineEdit) are returned as their own type.
        """
        return cls(item_type, ListAdapter(item_type, items), **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_adapter(cls, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_ModelGridOptionInputs]) -> Self:
        """
        Create an instance from any CollectionAdapter.
        Equivalent to the constructor — provided for API symmetry with ModelForm.from_adapter().
        Return type is Self so subclasses (e.g. ModelGridInlineEdit) are returned as their own type.
        """
        return cls(item_type, adapter, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_json(cls, item_type: type[T], path_name: Path, create_if_not_exist: bool = True, **kwargs: Unpack[_ModelGridOptionInputs]) -> Self:
        """
        Create an instance backed by a JSON file via JsonListAdapter.
        The file is created with an empty list if it does not exist.
        Call grid.adapter.reload() + grid.update_rows() to refresh from disk.
        Return type is Self so subclasses (e.g. ModelGridInlineEdit) are returned as their own type.
        """
        adapter = JsonListAdapter(item_type, path_name, create_if_not_exist=create_if_not_exist)
        return cls(item_type, adapter, **kwargs)  # type: ignore[arg-type]

    @property
    def adapter(self) -> CollectionAdapter:
        """The backing data adapter."""
        return self._data

    # --- event handler configuration --------------------------------------

    def on_select(self, callback: Handler[ValueChangeEventArguments]) -> Self:
        """
        Add a callback invoked when the row selection changes.
        Only meaningful when rowSelection='single'.
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        if self._rowSelection != 'single':
            log.warning(f"on_select is only supported for single row selection, but rowSelection is '{self._rowSelection}'")
        self._selection_handlers.append(callback)
        return self

    # --- data and rendering -----------------------------------------------

    def update_rows(self) -> Self:
        """Refresh the displayed rows from the adapter."""
        # _rows is mutated in-place (clear + re-append) so that widget.options['rowData'],
        # which holds the same list reference, stays in sync via NiceGUI's data binding —
        # the browser update happens automatically without an explicit widget.update() call.
        # self.widget.update()
        self._rows.clear()
        for item in self._data:
            row: dict[str, Any] = {'__ui_row_key': self._data.key_from_item(item)}
            for field_name in self._fields:
                field_info = self._fields[field_name]
                if field_info.hidden or field_info.table_hidden:
                    continue
                value = getattr(item, field_name)
                if field_name in self._cell_renderers:
                    row[field_name] = self._cell_renderers[field_name](value)
                elif isinstance(value, list):
                    row[field_name] = ', '.join(str(v) for v in value)
                elif isinstance(value, BaseModel):
                    row[field_name] = str(value)
                else:
                    row[field_name] = value
            self._rows.append(row)
        if self.widget:
            self.widget.options['rowData'] = self._rows
        return self

    def render(self) -> Self:
        """Render the ag-Grid widget into the current NiceGUI context."""
        cols = _collect_aggrid_cols(self._fields)
        self.update_rows()

        aggrid_kwargs: dict[str, Any] = {}
        if self._theme:
            aggrid_kwargs['theme'] = self._theme
        if self._auto_size_columns is not None:
            aggrid_kwargs['auto_size_columns'] = self._auto_size_columns
        config: dict[str, Any] = {
            'columnDefs': cols,
            'rowData': self._rows,
            'stopEditingWhenCellsLoseFocus': True,
        }
        if self._defaultColDef:
            config['defaultColDef'] = self._defaultColDef
        if self._rowSelection:
            config['rowSelection'] = self._rowSelection

        self.widget = ui.aggrid(config, **aggrid_kwargs)
        self.widget.on('selectionChanged', self._handle_selection_changed)

        if not self._auto_update_registered and isinstance(self._data, ReactiveAdapter):
            def _refresh() -> None:
                self.update_rows()
            self._data.on_change(_refresh)
            self._auto_update_registered = True

        return self

    async def _handle_selection_changed(self, event) -> None:
        if not self.widget:
            return
        row = await self.widget.get_selected_row()
        vce = ValueChangeEventArguments(sender=event.sender, client=event.client, value=row, previous_value=None)
        for handler in self._selection_handlers:
            handle_event(handler, vce)


@dataclass(kw_only=True, slots=True)
class TableItemEventArguments(ClickEventArguments):
    grid: ModelGrid
    row_key: str
    item: Any


@dataclass(kw_only=True, slots=True)
class TableItemFieldEventArguments(TableItemEventArguments):
    field_name: str
    new_value: Any


class _InlineEditableModelGridOptionInputs(_ModelGridOptionInputs, total=False):
    cell_readers: dict[str, Callable[[str], Any]]


class ModelGridInlineEdit(ModelGrid):
    """
    Extends ModelGrid with inline cell editing.
    Each cell edit is validated against the Pydantic model and persisted via the adapter.
    Register on_change() callbacks to react to successful or failed cell edits.
    """
    _change_handlers: list[Handler[TableItemFieldEventArguments]]
    cell_readers: dict[str, Callable[[str], Any]]

    def __init__(self, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_InlineEditableModelGridOptionInputs]) -> None:
        self.cell_readers = kwargs.pop('cell_readers', {})
        super().__init__(item_type, adapter, **kwargs)  # type: ignore[arg-type, misc]
        self._defaultColDef.update({'editable': True})
        self._change_handlers = []

    def on_change(self, callback: Handler[TableItemFieldEventArguments]) -> Self:
        """Add a callback invoked on each inline cell edit (success or validation failure)."""
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._change_handlers.append(callback)
        return self

    def render(self) -> Self:
        """Render the grid with inline editing enabled."""
        super().render()
        if self.widget:
            self.widget.on('cellValueChanged', self._handle_cell_value_changed)
        return self

    def _handle_cell_value_changed(self, event) -> None:
        row_key = event.args['data']['__ui_row_key']
        field_name = event.args['colId']
        old_value = event.args['oldValue']
        new_value = event.args['newValue']

        if field_name in self.cell_readers:
            old_value = self.cell_readers[field_name](old_value)
            new_value = self.cell_readers[field_name](new_value)

        try:
            item = self._data.read(row_key)
        except Exception:
            ui.notify(f"Row {row_key} not found — try again", color='negative')
            return

        if not isinstance(item, self._fields._item_type):
            log.error(f"Expected {self._fields._item_type.__name__}, got {type(item).__name__} for row {row_key}")
            return
        if not hasattr(item, field_name):
            log.error(f"Field '{field_name}' not found in {type(item).__name__}")
            return

        dumped = item.model_dump()
        dumped[field_name] = new_value
        errors = self._fields.validation_error_list(dumped)

        if not errors:
            setattr(item, field_name, new_value)
            try:
                self._data.update(item)
            except ConflictError:
                ui.notify('This item was changed by another user. The list has been refreshed — please edit again.', color='negative')
                self.update_rows()
                return
            except Exception as e:
                log.error(f'Error persisting cell edit for row {row_key}: {e}')
                ui.notify(f'Error saving change: {e}', color='negative')
                self.update_rows()
                return
        else:
            ui.notify(f"Invalid value {new_value!r}: {errors}", color='negative')
            self.update_rows()

        tife = TableItemFieldEventArguments(
            sender=event.sender, client=event.client,
            grid=self,
            row_key=row_key,
            item=item,
            field_name=field_name,
            new_value=new_value,
        )
        for handler in self._change_handlers:
            handle_event(handler, tife)
