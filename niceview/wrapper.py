import logging
from pathlib import Path
from typing import Self, Unpack
from fastapi import HTTPException
import typing_extensions
from pydantic import BaseModel
from nicegui import ui
from nicegui.events import Handler, ClickEventArguments, handle_event

from niceview.dataadapter import CollectionAdapter, ItemAdapter, ReloadableAdapter
from niceview.form import ModelForm, FieldChangeEventArguments
from niceview.grid import ModelGridInlineEdit, ModelGrid, T, TableItemEventArguments
from niceview.util import submit_dialog

log = logging.getLogger('niceview')


class _EditGridWrapperInputs(typing_extensions.TypedDict, total=False):
    title: str | None
    description: str | None
    delete_button: str | None
    add_button: str | None
    edit_button: str | None
    refresh_button: str | None


_GRID_WRAPPER_INPUT_KEYS = set(_EditGridWrapperInputs.__annotations__.keys())


class EditGridWrapper():
    """
    Chrome wrapper for ModelGrid: renders title, description, and CRUD buttons
    (add, edit, delete, refresh) above the grid.

    After render(), the NiceGUI elements are exposed for further styling:
        wrapper.title          → ui.label | None
        wrapper.description    → ui.markdown | None
        wrapper.title_row      → ui.row | None
        wrapper.add_button     → ui.button | None
        wrapper.edit_button    → ui.button | None
        wrapper.delete_button  → ui.button | None
        wrapper.refresh_button → ui.button | None
    """
    grid: ModelGrid

    # private config
    _rendered: bool
    _title: str | None
    _description: str | None
    _delete_button: str | None
    _add_button: str | None
    _edit_button: str | None
    _refresh_button: str | None

    # Exposed NiceGUI elements (populated by render())
    title: ui.label | None
    description: ui.markdown | None
    title_row: ui.row | None
    delete_button: ui.button | None
    add_button: ui.button | None
    edit_button: ui.button | None
    refresh_button: ui.button | None

    _change_handlers: list[Handler[TableItemEventArguments]]
    _model_repositories: dict[type[BaseModel], CollectionAdapter]

    def __init__(self, grid: ModelGrid, **kwargs: Unpack[_EditGridWrapperInputs]) -> None:
        self.grid = grid
        if self.grid._rowSelection and self.grid._rowSelection != 'single':
            raise ValueError(f"EditGridWrapper only supports single row selection, got '{self.grid._rowSelection}'")
        self.grid._rowSelection = 'single'

        default_edit = None if isinstance(self.grid, ModelGridInlineEdit) else ''
        self._title = kwargs.pop('title', f'{self.grid._fields._item_type.__name__} List')
        self._description = kwargs.pop('description', None)
        self._delete_button = kwargs.pop('delete_button', '')
        self._add_button = kwargs.pop('add_button', '')
        self._edit_button = kwargs.pop('edit_button', default_edit)
        self._refresh_button = kwargs.pop('refresh_button', '')

        self._rendered = False
        self.title = None
        self.description = None
        self.title_row = None
        self.delete_button = None
        self.add_button = None
        self.edit_button = None
        self.refresh_button = None

        self._change_handlers = []
        self._model_repositories = {}

    # --- factory methods ---------------------------------------------------

    @classmethod
    def from_list(cls, item_type: type[T], items: list[T], *, inline_edit: bool = False, **kwargs) -> Self:
        """Create an EditGridWrapper backed by an in-memory list. Renders immediately."""
        wrapper_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in _GRID_WRAPPER_INPUT_KEYS}
        grid_cls = ModelGridInlineEdit if inline_edit else ModelGrid
        grid = grid_cls.from_list(item_type, items, **kwargs)
        instance = cls(grid, **wrapper_kwargs)  # type: ignore[arg-type]
        instance.render()
        return instance

    @classmethod
    def from_json(cls, item_type: type[T], path_name: Path, create_if_not_exist: bool = True, *, inline_edit: bool = False, **kwargs) -> Self:
        """Create an EditGridWrapper backed by a JSON file. Renders immediately."""
        wrapper_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in _GRID_WRAPPER_INPUT_KEYS}
        grid_cls = ModelGridInlineEdit if inline_edit else ModelGrid
        grid = grid_cls.from_json(item_type, path_name, create_if_not_exist, **kwargs)
        instance = cls(grid, **wrapper_kwargs)  # type: ignore[arg-type]
        instance.render()
        return instance

    @classmethod
    def from_adapter(cls, item_type: type[T], adapter: CollectionAdapter, *, inline_edit: bool = False, **kwargs) -> Self:
        """Create an EditGridWrapper backed by any CollectionAdapter. Renders immediately."""
        wrapper_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in _GRID_WRAPPER_INPUT_KEYS}
        grid_cls = ModelGridInlineEdit if inline_edit else ModelGrid
        grid = grid_cls.from_adapter(item_type, adapter, **kwargs)
        instance = cls(grid, **wrapper_kwargs)  # type: ignore[arg-type]
        instance.render()
        return instance

    # --- configuration -----------------------------------------------------

    def with_repositories(self, repositories: 'dict[type[BaseModel], CollectionAdapter]') -> Self:
        """Set model repositories used for modelselect widgets in create/edit dialogs."""
        self._model_repositories = repositories
        return self

    def on_change(self, callback: Handler[TableItemEventArguments]) -> Self:
        """Add a callback invoked after each successful create, update, or delete."""
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._change_handlers.append(callback)
        return self

    def _notify_change_handlers(self, row_key: str, item: BaseModel | None) -> None:
        """Fire change handlers. Requires the grid to be rendered (widget must not be None)."""
        if not self._change_handlers:
            return
        widget = self.grid.widget
        if widget is None:
            return
        tce = TableItemEventArguments(
            sender=widget,  # type: ignore[arg-type]
            client=widget.client,  # type: ignore[attr-defined]
            grid=self.grid,
            row_key=row_key,
            item=item,
        )
        for handler in self._change_handlers:
            handle_event(handler, tce)

    async def _get_selected_row_key(self) -> str | None:
        """Return the row key of the currently selected row, or None if no row is selected."""
        if not self.grid.widget:
            return None
        selected_row = await self.grid.widget.get_selected_row()
        return selected_row['__ui_row_key'] if selected_row else None

    def _error_msg_from_exception(self, e: Exception) -> str:
        """Return a user-facing error message extracted from an exception."""
        if isinstance(e, HTTPException) and hasattr(e, 'detail'):
            return e.detail
        return str(e)

    # --- render ------------------------------------------------------------

    def render(self) -> Self:
        """Render title, description, CRUD buttons, and the grid into the current NiceGUI context."""
        if self._rendered:
            return self
        self.title = None
        self.description = None
        self.title_row = None
        self.delete_button = None
        self.add_button = None
        self.edit_button = None
        self.refresh_button = None

        has_buttons = any(b is not None for b in [self._refresh_button, self._delete_button, self._add_button, self._edit_button])
        has_chrome = bool(self._title) or has_buttons
        if has_chrome:
            with ui.row().classes('w-full items-center flex-nowrap') as self.title_row:
                if self._title:
                    self.title = ui.label(self._title).classes('text-h6 grow')
                if has_buttons:
                    if not self._title:
                        ui.space()
                    with ui.button_group().style('width: fit-content; flex: none'):
                        if self._refresh_button is not None:
                            self.refresh_button = ui.button(self._refresh_button, icon='refresh').props('dense flat').on_click(self._on_refresh_clicked)
                            with self.refresh_button:
                                ui.tooltip('Refresh').style('width: fit-content')
                        if self._delete_button is not None:
                            self.delete_button = ui.button(self._delete_button, icon='delete').props('color=negative dense flat').on_click(self._on_delete_clicked)
                            with self.delete_button:
                                ui.tooltip('Delete selected item').style('width: fit-content')
                        if self._add_button is not None:
                            self.add_button = ui.button(self._add_button, icon='add').props('dense flat').on_click(self._on_create_clicked)
                            with self.add_button:
                                ui.tooltip('Add a new item').style('width: fit-content')
                        if self._edit_button is not None:
                            self.edit_button = ui.button(self._edit_button, icon='edit').props('dense flat').on_click(self._on_update_clicked)
                            with self.edit_button:
                                ui.tooltip('Edit item').style('width: fit-content')

        if self._description:
            self.description = ui.markdown(self._description)

        self.grid.render()
        self._rendered = True
        return self

    # --- CRUD actions ------------------------------------------------------

    def refresh(self) -> None:
        """Reload from the adapter and re-render the grid."""
        if isinstance(self.grid.adapter, ReloadableAdapter):
            self.grid.adapter.reload()
        self.grid.update_rows()

    def _on_refresh_clicked(self, event: ClickEventArguments) -> None:
        self.refresh()

    def _apply_create(self, item: BaseModel) -> BaseModel:
        """Persist a new item via the adapter. Raises on type mismatch or adapter error."""
        return self.grid.adapter.create(item)

    def _apply_update(self, new_item: BaseModel, row_key: str) -> BaseModel:
        """Persist an updated item via the adapter. Raises on not-found or optimistic-lock conflict."""
        original = self.grid.adapter.read(row_key)
        for field, value in new_item.model_dump().items():
            setattr(original, field, value)
        return self.grid.adapter.update(original)

    def _apply_delete(self, row_key: str) -> None:
        """Delete an item via the adapter. Raises if the key does not exist."""
        self.grid.adapter.delete(row_key)

    async def create_item(self) -> None:
        """Open the create dialog and, on confirmation, persist the new item."""
        from niceview.dataadapter import FilteredAdapter
        item = self.grid._fields._item_type()
        # Pre-apply FK defaults so the dialog form starts with a valid item
        # (e.g. author_id is set before Pydantic validates the new Book).
        if isinstance(self.grid.adapter, FilteredAdapter):
            for field, value in self.grid.adapter._defaults.items():
                setattr(item, field, value)
        success = await self.default_edit_create_handler(item, True)
        if success:
            try:
                item = self._apply_create(item)
                ui.notify('Item created', color='positive')
                self.grid.update_rows()
                self._notify_change_handlers(self.grid.adapter.key_from_item(item), item)
            except Exception as e:
                log.error(f'Error creating item: {e}')
                ui.notify(f'Error creating item: {self._error_msg_from_exception(e)}', color='negative')
        else:
            ui.notify('Item creation cancelled', color='negative')

    async def _on_create_clicked(self, event: ClickEventArguments) -> None:
        await self.create_item()

    async def update_item(self) -> None:
        """Open the edit dialog for the selected row and, on confirmation, persist changes."""
        row_key = await self._get_selected_row_key()
        if not row_key:
            ui.notify('Please select a row first!', color='negative')
            return

        item = self.grid.adapter.read(row_key)
        if not item:
            ui.notify(f'Item with key {row_key} not found', color='negative')
            return

        item = item.model_copy(deep=True)
        success = await self.default_edit_create_handler(item, False)
        if not success:
            ui.notify('Item update cancelled', color='negative')
            return

        try:
            item = self._apply_update(item, row_key)
            ui.notify('Item updated', color='positive')
            self.grid.update_rows()
            self._notify_change_handlers(self.grid.adapter.key_from_item(item), item)
        except Exception as e:
            log.error(f'Error updating item: {e}')
            ui.notify(f'Error updating item: {self._error_msg_from_exception(e)}', color='negative')
            self.grid.update_rows()  # refresh to revert the UI to the current adapter state

    async def _on_update_clicked(self, event: ClickEventArguments) -> None:
        await self.update_item()

    async def delete_item(self) -> None:
        """Ask for confirmation and delete the selected row."""
        row_key = await self._get_selected_row_key()
        if not row_key:
            ui.notify('Please select a row for deletion!', color='negative')
            return

        confirm = await submit_dialog('Confirm Deletion', f'Are you sure you want to delete the selected item *{row_key}*?')
        if not confirm:
            ui.notify('Item deletion cancelled', color='negative')
            return

        try:
            self._apply_delete(row_key)
            ui.notify('Item deleted', color='positive')
            self.grid.update_rows()
            self._notify_change_handlers(row_key, None)
        except Exception as e:
            log.error(f'Error deleting item {row_key}: {e}')
            ui.notify(f'Error deleting item {row_key}: {self._error_msg_from_exception(e)}', color='negative')
            self.grid.update_rows()  # refresh to revert the UI to the current adapter state

    async def _on_delete_clicked(self, event: ClickEventArguments) -> None:
        await self.delete_item()

    async def default_edit_create_handler(self, item: BaseModel, do_create: bool) -> bool:
        """
        Show a modal dialog to create or edit an item. Returns True if the user confirmed.

        The dialog renders a ModelForm for the item and presents Cancel / Create-or-Ok buttons.
        On confirm, pending widget values are flushed into the validated item before the dialog
        closes — this guards against the edge case where a blur event arrives after the click
        over WebSocket (browsers fire blur before click, but message ordering is not guaranteed).
        """
        form = ModelForm.from_item(item)
        if self._model_repositories:
            form.with_repositories(self._model_repositories)

        def confirm():
            if form.has_validation_errors:
                ui.notify('Cannot save form: validation errors present', color='negative')
                return

            # Flush any pending widget values into the validated item.
            if form._current_item is not None and form._validated_item is not None:
                for field_name in form._fields:
                    fi = form._fields[field_name]
                    if not fi or fi.widget_type in ('editgrid', None):
                        continue
                    if form._validation_error_messages.get(field_name):
                        continue
                    cur = getattr(form._current_item, field_name)
                    if cur != getattr(form._validated_item, field_name):
                        setattr(form._validated_item, field_name, cur)
            dialog.submit('confirm')

        with ui.dialog().style('width: 400px') as dialog:
            with ui.card().classes('w-full'):
                form.render()
                with ui.card_section().classes('w-full'):
                    with ui.row():
                        ui.space()
                        ui.button('Cancel', on_click=lambda: dialog.submit('cancel'))
                        ui.button('Create' if do_create else 'Ok', on_click=confirm)

        success = ('confirm' == await dialog)
        dialog.clear()
        return success


class _EditFormWrapperInputs(typing_extensions.TypedDict, total=False):
    title: str | None
    description: str | None
    save_button: str | None
    refresh_button: str | None


_FORM_WRAPPER_INPUT_KEYS = set(_EditFormWrapperInputs.__annotations__.keys())


class EditFormWrapper():
    """
    Chrome wrapper for ModelForm: renders title, description, and action buttons
    (save, refresh) above the form fields.

    Intelligent button presets based on the factory method used:
    - from_item():    no buttons by default (in-memory, no adapter)
    - from_json():    save + refresh shown by default (adapter exists)
    - from_adapter(): save + refresh shown by default (adapter exists)
    Autosave suppresses the save button regardless.

    After render(), the NiceGUI elements are exposed for further styling:
        wrapper.title          → ui.label | None
        wrapper.save_button    → ui.button | None
        wrapper.refresh_button → ui.button | None
    """
    _rendered: bool
    _title: str | None
    _description: str | None
    _save_button: str | None
    _refresh_button: str | None

    # Exposed NiceGUI elements (populated by render())
    title: ui.label | None
    save_button: ui.button | None
    refresh_button: ui.button | None
    title_row: ui.row | None
    description: ui.markdown | None
    form: ModelForm

    def __init__(self, form: ModelForm, **kwargs: Unpack[_EditFormWrapperInputs]) -> None:
        has_adapter = form.adapter_bound
        autosave = form.autosave

        self._title = kwargs.pop('title', None)
        self._description = kwargs.pop('description', None)

        # Intelligent presets: show save/refresh when adapter exists, hide when autosave
        default_save = None if autosave else ('' if has_adapter else None)
        default_refresh = '' if has_adapter else None
        self._save_button = kwargs.pop('save_button', default_save)
        self._refresh_button = kwargs.pop('refresh_button', default_refresh)

        self._rendered = False
        self.title = None
        self.save_button = None
        self.refresh_button = None
        self.title_row = None
        self.description = None
        self.form = form

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments for EditFormWrapper: {', '.join(kwargs.keys())}")

    # --- factory methods ---------------------------------------------------

    @classmethod
    def from_item(cls, item_type_or_item: 'type[BaseModel] | BaseModel', item: 'BaseModel | None' = None, **kwargs) -> Self:
        """Create an EditFormWrapper backed by an in-memory item. Renders immediately."""
        wrapper_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in _FORM_WRAPPER_INPUT_KEYS}
        repositories: 'dict | None' = kwargs.pop('repositories', None)
        form = ModelForm.from_item(item_type_or_item, item, **kwargs)
        if repositories:
            form.with_repositories(repositories)
        instance = cls(form, **wrapper_kwargs)
        instance.render()
        return instance

    @classmethod
    def from_json(cls, item_type: type[BaseModel], json_path: Path, create_if_not_exist: bool = True, lock_field: str | None = None, created_field: str | None = None, **kwargs) -> Self:
        """Create an EditFormWrapper backed by a JSON file. Renders immediately with Save and Refresh buttons."""
        wrapper_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in _FORM_WRAPPER_INPUT_KEYS}
        repositories: 'dict | None' = kwargs.pop('repositories', None)
        form = ModelForm.from_json(item_type, json_path, create_if_not_exist, lock_field=lock_field, created_field=created_field, **kwargs)
        if repositories:
            form.with_repositories(repositories)
        instance = cls(form, **wrapper_kwargs)
        instance.render()
        return instance

    @classmethod
    def from_adapter(cls, item_type: type[BaseModel], adapter: 'CollectionAdapter | ItemAdapter', key: str | None = None, **kwargs) -> Self:
        """Create an EditFormWrapper backed by an adapter. Renders immediately with Save and Refresh buttons.

        With key: wraps CollectionAdapter + key in a BoundItem.
        Without key: treats adapter directly as an ItemAdapter (e.g. JsonAdapter).
        """
        wrapper_kwargs = {k: kwargs.pop(k) for k in list(kwargs) if k in _FORM_WRAPPER_INPUT_KEYS}
        repositories: 'dict | None' = kwargs.pop('repositories', None)
        form = ModelForm.from_adapter(item_type, adapter, key, **kwargs)
        if repositories:
            form.with_repositories(repositories)
        instance = cls(form, **wrapper_kwargs)
        instance.render()
        return instance

    # --- delegation --------------------------------------------------------

    def with_repositories(self, repositories: 'dict[type[BaseModel], CollectionAdapter]') -> Self:
        """Delegate to the inner ModelForm."""
        self.form.with_repositories(repositories)
        return self

    def on_change(self, callback: Handler[FieldChangeEventArguments]) -> Self:
        """Delegate to the inner ModelForm's on_change."""
        self.form.on_change(callback)
        return self

    def load(self, adapter: 'ItemAdapter | CollectionAdapter', key: str | None = None) -> Self:
        """
        Load a specific item (master-detail navigation). Delegates to ModelForm.load().

        Two call forms:
          load(item_adapter)    — any ItemAdapter (BoundItem, JsonAdapter, …)
          load(collection, key) — convenience: wraps in BoundItem internally
        """
        if key is not None:
            self.form.load(adapter, key)  # type: ignore[arg-type]
        else:
            self.form.load(adapter)  # type: ignore[arg-type]
        return self

    # --- render ------------------------------------------------------------

    def render(self) -> Self:
        """Render title, description, action buttons, and the form into the current NiceGUI context."""
        if self._rendered:
            return self
        self.title = None
        self.save_button = None
        self.refresh_button = None
        self.title_row = None
        self.description = None

        has_chrome = bool(self._title) or any(
            b is not None for b in [self._save_button, self._refresh_button]
        )
        if has_chrome:
            with ui.row().classes('w-full items-center flex-nowrap') as self.title_row:
                if self._title:
                    self.title = ui.label(self._title).classes('text-h6 grow')
                if self._refresh_button is not None or self._save_button is not None:
                    if not self._title:
                        ui.space()
                    with ui.button_group().style('width: fit-content; flex: none'):
                        if self._refresh_button is not None:
                            self.refresh_button = ui.button(self._refresh_button, icon='refresh').props('dense flat').on_click(lambda _: self.form.refresh())
                            with self.refresh_button:
                                ui.tooltip('Refresh').style('width: fit-content')
                        if self._save_button is not None:
                            self.save_button = ui.button(self._save_button, icon='save').props('dense flat').on_click(lambda _: self.form.save())
                            with self.save_button:
                                ui.tooltip('Save').style('width: fit-content')

        if self._description:
            self.description = ui.markdown(self._description)

        self.form.render()
        self._rendered = True
        return self
