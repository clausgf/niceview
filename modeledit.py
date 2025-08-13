from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Iterable, Self, Unpack
import typing_extensions
from pydantic import BaseModel, ValidationError
from nicegui import ui
from nicegui.events import Handler, UiEventArguments, ValueChangeEventArguments, ClickEventArguments, handle_event
from nicegui.dataclasses import KWONLY_SLOTS

from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGridInlineEdit, ModelDataAdapter, ModelGrid, T, TableItemEventArguments, TableItemFieldEventArguments


class _EditGridWrapperInputs(typing_extensions.TypedDict, total=False):
    title: str
    delete_button: str
    add_button: str
    edit_button: str
    refresh_button: str


class EditGridWrapper():
    """
    A table class that can be used to create editable tables for Pydantic models.
    """
    grid: ModelGrid
    title: str
    description: str | None
    delete_button: str | None
    add_button: str | None
    edit_button: str | None
    refresh_button: str | None

    _change_handlers: list[Handler[TableItemEventArguments]]

    def __init__(self, grid: ModelGrid, **kwargs: Unpack[_EditGridWrapperInputs]) -> None:
        self.grid = grid
        if self.grid.rowSelection and grid.rowSelection != 'single':
            raise ValueError("EditableModelGrid only supports single row selection, but got {grid.rowSelection}")
        self.grid.rowSelection = 'single'

        default_edit = None if isinstance(self.grid, ModelGridInlineEdit) else ''
        self.title = kwargs.pop('title', f'{self.grid._fields._item_type.__name__} List')
        self.delete_button = kwargs.pop('delete_button', '')
        self.add_button = kwargs.pop('add_button', '')
        self.edit_button = kwargs.pop('edit_button', default_edit)
        self.refresh_button = kwargs.pop('refresh_button', '')

        self._change_handlers = []


    def on_change(self, callback: Handler[TableItemEventArguments]) -> Self:
        """
        Add a callback to be invoked when the form values change after successful validation. 
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._change_handlers.append(callback)
        return self
    

    def _invoke_change_handlers(self, event: ClickEventArguments, row_key: str, item: BaseModel | None) -> None:
        """
        Invoke the change handlers with the given event, row key and item.
        """
        tce = TableItemEventArguments(
            sender=event.sender, client=event.client, 
            model_table=self.grid,
            row_key=row_key, 
            item=item
        )
        for handler in self._change_handlers:
            handle_event(handler, tce)


    def render(self) -> Self:
        """
        Render the grid with the title and buttons.
        """
        # render the title, add and delete buttons
        with ui.row().classes('w-full'):
            if self.title:
                ui.label(self.title).classes('text-h6')
            ui.space()
            with ui.button_group():
                if self.refresh_button is not None:
                    ui.button(self.refresh_button, icon='refresh').tooltip('Refresh').props('dense flat').on_click(self.refresh)
                if self.delete_button is not None:
                    ui.button(self.delete_button, icon='delete').props('color=red').props('dense flat').tooltip('Delete selected item').on_click(self.delete_item)
                if self.add_button is not None:
                    ui.button(self.add_button, icon='add').tooltip('Add a new item').props('dense flat').on_click(self.create_item)
                if self.edit_button is not None:
                    ui.button(self.edit_button, icon='edit').tooltip('Edit item').props('dense flat').on_click(self.update_item)

        self.grid.render()
        return self


    def refresh(self, event: ClickEventArguments) -> None:
        self.grid.update_rows()


    async def create_item(self, event: ClickEventArguments) -> None:
        item = self.grid._fields._item_type()
        success = await self.default_edit_create_handler(item, True)
        if success:
            try:
                item = self.grid._data.create(item)
                ui.notify(f'Item created', color='positive')
            except Exception as e:
                print(f'Error creating item: {e}')
                ui.notify(f'Error creating item: {e}', color='negative')
        else:
            ui.notify('Item creation cancelled', color='negative')

        self.grid.update_rows()
        self._invoke_change_handlers(event, self.grid._data.key_from_item(item), item)


    async def update_item(self, event: ClickEventArguments) -> None:
        selected_row = await self.grid.widget.get_selected_row()
        if not selected_row:
            ui.notify('Please select a row for editing', color='negative')
            return
        row_key = selected_row['__ui_row_key']

        item = self.grid._data.read(row_key)
        if not item:
            ui.notify(f'Item with key {row_key} not found', color='negative')
            return

        # edit & update the item
        item = item.model_copy(deep=True)  # make sure to edit a copy of the item
        success = await self.default_edit_create_handler(item, False)
        if success:
            try:
                item = self.grid._data.update(item, row_key)
                ui.notify(f'Item updated', color='positive')
            except Exception as e:
                ui.notify(f'Error updating item: {e}', color='negative')
        else:
            ui.notify('Item update cancelled', color='negative')
            return

        self.grid.update_rows()
        self._invoke_change_handlers(event, self.grid._data.key_from_item(item), item)


    async def delete_item(self, event: ClickEventArguments) -> None:
        # determine the selected rows to delete from the grid widget
        selected_row = await self.grid.widget.get_selected_row()
        if not selected_row:
            ui.notify('Please select a row for deletion', color='negative')
            return
        row_key = selected_row['__ui_row_key']

        # delete the item from the data adapter
        try:
            self.grid._data.delete(row_key)
            ui.notify(f'Item deleted', color='positive')
        except Exception as e:
            ui.notify(f'Error deleting item {row_key}: {e}', color='negative')

        self.grid.update_rows()
        self._invoke_change_handlers(event, row_key, None)


    async def default_edit_create_handler(self, item: BaseModel, do_create: bool) -> bool:
        """
        Default edit handler that shows a dialog to edit the item.
        """
        form = ModelForm(item, classes='w-full')
        with ui.dialog().style('width: 400px') as dialog:
            with ui.card().classes('w-full'):
                form.render()
                #ui.separator()
                with ui.card_section():
                    with ui.row():
                        ui.space()
                        ui.button('Cancel', on_click=lambda: dialog.submit('cancel'))
                        ui.button('Create' if do_create else 'Ok', on_click=lambda: dialog.submit('confirm'))

        success = ('confirm' == await dialog)
        dialog.clear()
        return success


class _EditFormWrapperInputs(typing_extensions.TypedDict, total=False):
    title: str
    autosave: bool
    refresh_button: str
    cancel_button: str
    apply_button: str
    ok_button: str


class EditFormWrapper():
    """
    A wrapper for a ModelForm that can be used to create editable forms for Pydantic models.
    """
    refresh_button: str | None
    cancel_button: str | None
    apply_button: str | None
    ok_button: str | None

    _form: ModelForm
    _change_handlers: list[Handler[UiEventArguments]]
    _item: BaseModel

    def __init__(self, form: ModelForm, **kwargs: Unpack[_EditFormWrapperInputs]) -> None:
        self._form = form
        self.title = kwargs.pop('title', f'{self._form._item_type.__name__} Form')
        self.autosave = kwargs.pop('autosave', False)
        self.refresh_button = kwargs.pop('refresh_button', None if self.autosave else '')
        self.cancel_button = kwargs.pop('cancel_button', None if self.autosave else '')
        self.apply_button = kwargs.pop('apply_button', None if self.autosave else '')
        self.ok_button = kwargs.pop('ok_button', None if self.autosave else '')

        self._change_handlers = []


    def on_change(self, callback: Handler[UiEventArguments]) -> Self:
        """
        Add a callback to be invoked when the form values change after successful validation. 
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._change_handlers.append(callback)
        return self


    def _invoke_change_handlers(self, event: UiEventArguments, item: BaseModel | None) -> None:
        """
        Invoke the change handlers with the given event, row key and item.
        """
        vce = ValueChangeEventArguments(
            sender=event.sender, client=event.client,
            value=item
        )
        for handler in self._change_handlers:
            handle_event(handler, vce)


    def render(self) -> Self:
        """
        Render the grid with the title and buttons.
        """
        # render the title, add and delete buttons
        #with ui.row().classes('w-full'):
        self._form.render()
        #    ui.space()
            # with ui.button_group():
            #     if self.refresh_button is not None:
            #         ui.button(self.refresh_button, icon='refresh').tooltip('Reload').props('dense flat').on_click(self.reload)
            #     if self.cancel_button is not None:
            #         ui.button(self.cancel_button, icon='cancel').props('color=secondary').props('dense flat').tooltip('Cancel').on_click(self.delete_item)
            #     if self.apply_button is not None:
            #         ui.button(self.apply_button, icon='apply').tooltip('Apply (i.e. save) changes').props('dense flat').on_click(self.create_item)
            #     if self.ok_button is not None:
            #         ui.button(self.ok_button, icon='ok').tooltip('Edit item').props('dense flat').on_click(self.update_item)

        return self

