import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self, Unpack, cast
from fastapi import HTTPException
import typing_extensions
from pydantic import BaseModel
from nicegui import ui
from nicegui.events import Handler, ClickEventArguments, UiEventArguments, handle_event

from niceview.dataadapter import CollectionAdapter, ConflictError, StorageError, ItemAdapter, ReloadableAdapter
from niceview.modelform import (FieldChangeEventArguments, FormAction, ModelForm,
                                _ModelFormOptionInputs, render_action_button)
from niceview.modelgrid import ModelGridInlineEdit, ModelGrid, T, TableItemEventArguments, _InlineEditableModelGridOptionInputs
from niceview.style import (ChromeStyle, NotifyKind, Place, chrome_button, chrome_buttons,
                            chrome_dialog, chrome_dialog_buttons, chrome_notify, chrome_row,
                            chrome_title, get_chrome_style)
from niceview.text import ChromeText, get_chrome_text, text_of
from niceview.util import confirm_dialog

log = logging.getLogger('niceview')


@dataclass(kw_only=True, slots=True)
class GridActionEventArguments(UiEventArguments):
    """
    What an action's `on_click` receives in an EditGridWrapper's title row.

    A grid has no item of its own, it has a selection: `row_key` and `item` are the selected
    row, or None when nothing is selected — which an action that works on one has to check,
    the same way Edit and Delete do.
    """
    wrapper: 'EditGridWrapper'
    name: str
    action: FormAction
    row_key: str | None
    item: BaseModel | None


class _EditGridWrapperInputs(typing_extensions.TypedDict, total=False):
    title: str | None
    description: str | None
    delete_button: str | None
    add_button: str | None
    edit_button: str | None
    refresh_button: str | None
    chrome_actions: dict[str, FormAction]
    """The application's own buttons in the title row, by name, left of niceview's own. Same
    FormAction as a form's `actions` — its `on_click` gets a GridActionEventArguments here."""
    chrome_style: ChromeStyle | None
    """Look of the title row and its buttons. Replaces the application-wide default of
    niceview.style.set_chrome_style() wholesale — derive it with ChromeStyle.derived()."""
    chrome_text: ChromeText | None
    """Texts of the tooltips, dialogs and notifications. Replaces the application-wide default
    of niceview.text.set_chrome_text() wholesale — derive it with ChromeText.derived()."""
    place: Place
    """Where this wrapper's buttons sit in the chrome cascade: 'toolbar' (default) for a wrapper
    of its own, 'form' for one embedded in a form."""


class _EditGridWrapperFactoryInputs(_EditGridWrapperInputs, _InlineEditableModelGridOptionInputs, total=False):
    """Options accepted by the EditGridWrapper factory methods: wrapper chrome plus all ModelGrid options."""


_GRID_WRAPPER_INPUT_KEYS = set(_EditGridWrapperInputs.__annotations__.keys())


class EditGridWrapper():
    """
    Chrome wrapper for ModelGrid: renders title, description, and CRUD buttons
    (add, edit, delete, refresh) above the grid.

    Title semantics: omitted or '' → auto-generated title '{ItemType} List';
    None → no title; any other string → that title.
    Button semantics ('' and None differ from the title!): '' → icon-only
    button (the default), a string → labeled button, None → button hidden.

    `chrome_actions` adds the application's own buttons to that row — the same `FormAction` a
    form places between its fields, here left of niceview's own so those keep the right edge
    they have everywhere. Their `on_click` receives a `GridActionEventArguments`, with the
    selected row rather than a form's item.

    After render(), the NiceGUI elements are exposed for further styling:
        wrapper.title          → ui.label | None
        wrapper.description    → ui.markdown | None
        wrapper.title_row      → ui.row | None
        wrapper.add_button     → ui.button | None
        wrapper.edit_button    → ui.button | None
        wrapper.delete_button  → ui.button | None
        wrapper.refresh_button → ui.button | None
        wrapper.action_buttons → dict[str, ui.button] — from chrome_actions=
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
    _chrome_actions: dict[str, FormAction]
    _chrome_style: ChromeStyle | None
    _chrome_text: ChromeText | None
    _place: Place

    # Exposed NiceGUI elements (populated by render())
    title: ui.label | None
    description: ui.markdown | None
    title_row: ui.row | None
    delete_button: ui.button | None
    add_button: ui.button | None
    edit_button: ui.button | None
    refresh_button: ui.button | None
    action_buttons: dict[str, ui.button]

    _change_handlers: list[Handler[TableItemEventArguments]]
    _model_repositories: dict[type[BaseModel], CollectionAdapter]

    def __init__(self, grid: ModelGrid, **kwargs: Unpack[_EditGridWrapperInputs]) -> None:
        self.grid = grid
        if self.grid._rowSelection and self.grid._rowSelection != 'single':
            raise ValueError(f"EditGridWrapper only supports single row selection, got '{self.grid._rowSelection}'")
        self.grid._rowSelection = 'single'

        default_edit = None if isinstance(self.grid, ModelGridInlineEdit) else ''
        title = kwargs.pop('title', '')
        self._title = f'{self.grid._fields._item_type.__name__} List' if title == '' else title
        self._description = kwargs.pop('description', None)
        self._delete_button = kwargs.pop('delete_button', '')
        self._add_button = kwargs.pop('add_button', '')
        self._edit_button = kwargs.pop('edit_button', default_edit)
        self._refresh_button = kwargs.pop('refresh_button', '')
        self._chrome_actions = ModelForm._checked_actions(kwargs.pop('chrome_actions', {}),
                                                          no_form="a grid's title row has none")
        self._chrome_style = kwargs.pop('chrome_style', None)
        self._chrome_text = kwargs.pop('chrome_text', None)
        self._place = kwargs.pop('place', 'toolbar')

        self._rendered = False
        self.title = None
        self.description = None
        self.title_row = None
        self.delete_button = None
        self.add_button = None
        self.edit_button = None
        self.refresh_button = None
        self.action_buttons = {}

        self._change_handlers = []
        self._model_repositories = {}

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments for EditGridWrapper: {', '.join(kwargs.keys())}")

    @property
    def _style(self) -> ChromeStyle:
        return self._chrome_style or get_chrome_style()

    @property
    def _text(self) -> ChromeText:
        return self._chrome_text or get_chrome_text()

    def _notify(self, template: Any, kind: 'NotifyKind', **params: Any) -> None:
        """One of niceview's notifications: text from ChromeText, delivery from ChromeStyle."""
        chrome_notify(text_of(template, **params), kind, self._style)

    # --- factory methods ---------------------------------------------------

    @classmethod
    def _split_kwargs(cls, kwargs: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """Split factory kwargs into (wrapper chrome options, ModelGrid options)."""
        grid_kwargs = dict(kwargs)
        wrapper_kwargs = {k: grid_kwargs.pop(k) for k in list(grid_kwargs) if k in _GRID_WRAPPER_INPUT_KEYS}
        return wrapper_kwargs, grid_kwargs

    @classmethod
    def from_list(cls, item_type: type[T], items: list[T], *, inline_edit: bool = False, **kwargs: Unpack[_EditGridWrapperFactoryInputs]) -> Self:
        """Create an EditGridWrapper backed by an in-memory list. Call render() (fluent: from_list(...).render()) to draw it."""
        wrapper_kwargs, grid_kwargs = cls._split_kwargs(kwargs)
        grid_cls = ModelGridInlineEdit if inline_edit else ModelGrid
        grid = grid_cls.from_list(item_type, items, **grid_kwargs)
        return cls(grid, **wrapper_kwargs)

    @classmethod
    def from_json(cls, item_type: type[T], path_name: Path, *, create_if_not_exist: bool = True, inline_edit: bool = False, **kwargs: Unpack[_EditGridWrapperFactoryInputs]) -> Self:
        """Create an EditGridWrapper backed by a JSON file. Call render() to draw it."""
        wrapper_kwargs, grid_kwargs = cls._split_kwargs(kwargs)
        grid_cls = ModelGridInlineEdit if inline_edit else ModelGrid
        grid = grid_cls.from_json(item_type, path_name, create_if_not_exist=create_if_not_exist, **grid_kwargs)
        return cls(grid, **wrapper_kwargs)

    @classmethod
    def from_adapter(cls, item_type: type[T], adapter: CollectionAdapter, *, inline_edit: bool = False, **kwargs: Unpack[_EditGridWrapperFactoryInputs]) -> Self:
        """Create an EditGridWrapper backed by any CollectionAdapter. Call render() to draw it."""
        wrapper_kwargs, grid_kwargs = cls._split_kwargs(kwargs)
        grid_cls = ModelGridInlineEdit if inline_edit else ModelGrid
        grid = grid_cls.from_adapter(item_type, adapter, **grid_kwargs)
        return cls(grid, **wrapper_kwargs)

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
        self.action_buttons = {}

        style, text, place = self._style, self._text, self._place
        button_count = sum(b is not None for b in [self._refresh_button, self._delete_button, self._add_button, self._edit_button]) + len(self._chrome_actions)
        has_chrome = bool(self._title) or button_count > 0
        if has_chrome:
            with chrome_row(style) as self.title_row:
                if self._title:
                    self.title = chrome_title(self._title, style)
                if button_count:
                    if not self._title:
                        ui.space()
                    with chrome_buttons(style, button_count):
                        for name, action in self._chrome_actions.items():
                            self.action_buttons[name] = render_action_button(
                                action, style, place, None,
                                lambda event, n=name, a=action: self._handle_chrome_action(n, a, event))
                        if self._refresh_button is not None:
                            self.refresh_button = chrome_button('refresh', self._refresh_button, 'refresh', text_of(text.refresh_tooltip), style, self._on_refresh_clicked, place)
                        if self._delete_button is not None:
                            self.delete_button = chrome_button('delete', self._delete_button, 'delete', text_of(text.delete_tooltip), style, self._on_delete_clicked, place)
                        if self._add_button is not None:
                            self.add_button = chrome_button('add', self._add_button, 'add', text_of(text.add_tooltip), style, self._on_create_clicked, place)
                        if self._edit_button is not None:
                            self.edit_button = chrome_button('edit', self._edit_button, 'edit', text_of(text.edit_tooltip), style, self._on_update_clicked, place)

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
                self._notify(self._text.item_created, 'positive')
                self.grid.update_rows()
                self._notify_change_handlers(self.grid.adapter.key_from_item(item), item)
            except Exception as e:
                log.error(f'Error creating item: {e}')
                self._notify(self._text.create_error, 'negative', error=self._error_msg_from_exception(e))
        else:
            self._notify(self._text.create_cancelled, 'negative')

    async def _on_create_clicked(self, event: ClickEventArguments) -> None:
        await self.create_item()

    async def update_item(self) -> None:
        """Open the edit dialog for the selected row and, on confirmation, persist changes."""
        row_key = await self._get_selected_row_key()
        if not row_key:
            self._notify(self._text.select_row_first, 'negative')
            return

        item = self.grid.adapter.read(row_key)
        if not item:
            self._notify(self._text.item_not_found, 'negative', key=row_key)
            return

        item = item.model_copy(deep=True)
        success = await self.default_edit_create_handler(item, False)
        if not success:
            self._notify(self._text.update_cancelled, 'negative')
            return

        try:
            item = self._apply_update(item, row_key)
            self._notify(self._text.item_updated, 'positive')
            self.grid.update_rows()
            self._notify_change_handlers(self.grid.adapter.key_from_item(item), item)
        except ConflictError as e:
            log.warning(f'Optimistic lock conflict updating item {row_key}: {e}')
            self._notify(self._text.conflict, 'negative')
            self.grid.update_rows()
        except StorageError as e:
            log.error(f'Storage error updating item {row_key}: {e}')
            self._notify(str(e), 'negative')  # the adapter's own message, not one of ours
            self.grid.update_rows()
        except Exception as e:
            log.error(f'Error updating item: {e}')
            self._notify(self._text.update_error, 'negative', error=self._error_msg_from_exception(e))
            self.grid.update_rows()  # refresh to revert the UI to the current adapter state

    async def _on_update_clicked(self, event: ClickEventArguments) -> None:
        await self.update_item()

    async def delete_item(self) -> None:
        """Ask for confirmation and delete the selected row."""
        row_key = await self._get_selected_row_key()
        if not row_key:
            self._notify(self._text.select_row_to_delete, 'negative')
            return

        text = self._text
        confirm = await confirm_dialog(text_of(text.delete_selected_title),
                                       text_of(text.delete_selected_message, key=row_key),
                                       ok_label=text_of(text.delete_label), ok_role='delete',
                                       chrome_style=self._chrome_style, chrome_text=self._chrome_text)
        if not confirm:
            self._notify(text.delete_cancelled, 'negative')
            return

        try:
            self._apply_delete(row_key)
            self._notify(text.item_deleted, 'positive')
            self.grid.update_rows()
            self._notify_change_handlers(row_key, None)
        except Exception as e:
            log.error(f'Error deleting item {row_key}: {e}')
            self._notify(text.delete_error, 'negative', key=row_key, error=self._error_msg_from_exception(e))
            self.grid.update_rows()  # refresh to revert the UI to the current adapter state

    async def _on_delete_clicked(self, event: ClickEventArguments) -> None:
        await self.delete_item()

    async def _handle_chrome_action(self, name: str, action: FormAction, event: ClickEventArguments) -> None:
        """Call one of the application's own title-row actions with the current selection."""
        if action.on_click is None:
            return
        row_key = await self._get_selected_row_key()  # async: the selection lives in the browser
        item: BaseModel | None = None
        if row_key is not None:
            try:
                item = self.grid.adapter.read(row_key)
            except (KeyError, ValueError):
                item = None  # deleted between the click and the answer — the action sees no item
        handle_event(cast('Handler[GridActionEventArguments]', action.on_click),
                     GridActionEventArguments(sender=event.sender, client=event.client,
                                              wrapper=self, name=name, action=action,
                                              row_key=row_key, item=item))

    async def default_edit_create_handler(self, item: BaseModel, do_create: bool) -> bool:
        """
        Show a modal dialog to create or edit an item. Returns True if the user confirmed.

        The dialog renders a ModelForm for the item and presents Cancel / Create-or-Ok buttons.
        On confirm, pending widget values are flushed into the validated item before the dialog
        closes — this guards against the edge case where a blur event arrives after the click
        over WebSocket (browsers fire blur before click, but message ordering is not guaranteed).
        """
        style, text = self._style, self._text
        form = ModelForm.from_item(item, chrome_style=self._chrome_style, chrome_text=self._chrome_text)
        if self._model_repositories:
            form.with_repositories(self._model_repositories)

        def confirm():
            if form.has_validation_errors:
                self._notify(text.validation_errors, 'negative')
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

        with chrome_dialog(style) as dialog:
            form.render()
            with ui.card_section().classes('w-full'):
                # Same button row as niceview.util's dialogs: cancel first, confirm last,
                # aligned to the right edge.
                with chrome_dialog_buttons(style):
                    chrome_button('cancel', text_of(text.cancel_label), None, '', style,
                                  lambda: dialog.submit('cancel'), place='dialog')
                    chrome_button('ok', text_of(text.create_label if do_create else text.ok_label),
                                  None, '', style, confirm, place='dialog')

        success = ('confirm' == await dialog)
        dialog.clear()
        return success


class _EditFormWrapperInputs(typing_extensions.TypedDict, total=False):
    title: str | None
    description: str | None
    save_button: str | None
    refresh_button: str | None
    chrome_actions: dict[str, 'FormAction']
    """The application's own buttons in the title row, by name, left of Refresh and Save. Same
    FormAction as the form's `actions` — the one that is placed in the layout as '@name'."""
    chrome_style: ChromeStyle | None
    """Look of the title row and its buttons. Replaces the application-wide default of
    niceview.style.set_chrome_style() wholesale — derive it with ChromeStyle.derived().
    Passed on to the wrapped ModelForm, whose section titles it styles too."""
    chrome_text: ChromeText | None
    """Texts of the tooltips and notifications. Replaces the application-wide default of
    niceview.text.set_chrome_text() wholesale — derive it with ChromeText.derived()."""
    place: Place
    """Where this wrapper's buttons sit in the chrome cascade: 'toolbar' (default) for a wrapper
    of its own, 'form' for one embedded in a form."""


class _EditFormWrapperFactoryInputs(_EditFormWrapperInputs, _ModelFormOptionInputs, total=False):  # type: ignore[misc]
    """Options accepted by the EditFormWrapper factory methods: wrapper chrome plus all ModelForm
    options. Both halves declare chrome_style and chrome_text, with the same type and the same
    meaning — the factory hands them to both the wrapper and the form it wraps."""
    repositories: dict[type[BaseModel], CollectionAdapter]


_FORM_WRAPPER_INPUT_KEYS = set(_EditFormWrapperInputs.__annotations__.keys())


def _split_form_kwargs(kwargs: Mapping[str, Any]) -> 'tuple[dict[str, Any], dict | None, dict[str, Any]]':
    """Split factory kwargs into (wrapper chrome options, repositories, ModelForm options)."""
    form_kwargs = dict(kwargs)
    wrapper_kwargs = {k: form_kwargs.pop(k) for k in list(form_kwargs) if k in _FORM_WRAPPER_INPUT_KEYS}
    repositories = form_kwargs.pop('repositories', None)
    # Style and texts belong to both: the wrapper draws the title row, the form the section
    # titles and the field markers below it. A style set on the wrapper styles its inside too.
    for shared in ('chrome_style', 'chrome_text'):
        if shared in wrapper_kwargs:
            form_kwargs[shared] = wrapper_kwargs[shared]
    return wrapper_kwargs, repositories, form_kwargs


class EditFormWrapper():
    """
    Chrome wrapper for ModelForm: renders title, description, and action buttons
    (save, refresh) above the form fields.

    Intelligent button presets based on the factory method used:
    - from_item():    no buttons by default (in-memory, no adapter)
    - from_json():    save + refresh shown by default (adapter exists)
    - from_adapter(): save + refresh shown by default (adapter exists)
    Autosave suppresses the save button regardless.

    `chrome_actions` adds the application's own buttons to that row — the same `FormAction` the
    form places between its fields, here left of Refresh and Save, so niceview's own buttons keep
    the right edge they always have.

    After render(), the NiceGUI elements are exposed for further styling:
        wrapper.title          → ui.label | None
        wrapper.save_button    → ui.button | None
        wrapper.refresh_button → ui.button | None
        wrapper.action_buttons → dict[str, ui.button]
    """
    _rendered: bool
    _title: str | None
    _description: str | None
    _save_button: str | None
    _refresh_button: str | None
    _chrome_actions: dict[str, FormAction]
    _chrome_style: ChromeStyle | None
    _chrome_text: ChromeText | None
    _place: Place

    # Exposed NiceGUI elements (populated by render())
    title: ui.label | None
    save_button: ui.button | None
    refresh_button: ui.button | None
    action_buttons: dict[str, ui.button]
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
        self._chrome_actions = ModelForm._checked_actions(kwargs.pop('chrome_actions', {}))
        self._chrome_style = kwargs.pop('chrome_style', None)
        self._chrome_text = kwargs.pop('chrome_text', None)
        self._place = kwargs.pop('place', 'toolbar')

        self._rendered = False
        self.title = None
        self.save_button = None
        self.refresh_button = None
        self.action_buttons = {}
        self.title_row = None
        self.description = None
        self.form = form

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments for EditFormWrapper: {', '.join(kwargs.keys())}")

    @property
    def _style(self) -> ChromeStyle:
        return self._chrome_style or get_chrome_style()

    @property
    def _text(self) -> ChromeText:
        return self._chrome_text or get_chrome_text()

    # --- factory methods ---------------------------------------------------

    @classmethod
    def from_item(cls, item_type_or_item: 'type[BaseModel] | BaseModel', item: 'BaseModel | None' = None, /, **kwargs: Unpack[_EditFormWrapperFactoryInputs]) -> Self:
        """Create an EditFormWrapper backed by an in-memory item. Call render() (fluent: from_item(...).render()) to draw it."""
        wrapper_kwargs, repositories, form_kwargs = _split_form_kwargs(kwargs)
        if isinstance(item_type_or_item, BaseModel):
            if item is not None:
                raise TypeError("When passing an item instance as the first argument, do not pass a second item")
            form = ModelForm.from_item(item_type_or_item, **form_kwargs)
        else:
            if item is None:
                raise TypeError("When passing an item type as the first argument, an item instance is required")
            form = ModelForm.from_item(item_type_or_item, item, **form_kwargs)
        if repositories:
            form.with_repositories(repositories)
        return cls(form, **wrapper_kwargs)

    @classmethod
    def from_json(cls, item_type: type[BaseModel], json_path: Path, *, create_if_not_exist: bool = True, lock_field: str | None = None, created_field: str | None = None, **kwargs: Unpack[_EditFormWrapperFactoryInputs]) -> Self:
        """Create an EditFormWrapper backed by a JSON file with Save and Refresh buttons. Call render() to draw it."""
        wrapper_kwargs, repositories, form_kwargs = _split_form_kwargs(kwargs)
        form = ModelForm.from_json(item_type, json_path, create_if_not_exist=create_if_not_exist, lock_field=lock_field, created_field=created_field, **form_kwargs)
        if repositories:
            form.with_repositories(repositories)
        return cls(form, **wrapper_kwargs)

    @classmethod
    def from_adapter(cls, item_type: type[BaseModel], adapter: 'CollectionAdapter | ItemAdapter', key: str | None = None, **kwargs: Unpack[_EditFormWrapperFactoryInputs]) -> Self:
        """Create an EditFormWrapper backed by an adapter with Save and Refresh buttons. Call render() to draw it.

        With key: wraps CollectionAdapter + key in a BoundItem.
        Without key: treats adapter directly as an ItemAdapter (e.g. JsonAdapter).
        """
        wrapper_kwargs, repositories, form_kwargs = _split_form_kwargs(kwargs)
        form = ModelForm.from_adapter(item_type, adapter, key, **form_kwargs)
        if repositories:
            form.with_repositories(repositories)
        return cls(form, **wrapper_kwargs)

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
        self.action_buttons = {}
        self.title_row = None
        self.description = None

        style, text, place = self._style, self._text, self._place
        button_count = sum(b is not None for b in [self._save_button, self._refresh_button]) + len(self._chrome_actions)
        has_chrome = bool(self._title) or button_count > 0
        if has_chrome:
            with chrome_row(style) as self.title_row:
                if self._title:
                    self.title = chrome_title(self._title, style)
                if button_count:
                    if not self._title:
                        ui.space()
                    with chrome_buttons(style, button_count):
                        for name, action in self._chrome_actions.items():
                            self.action_buttons[name] = self.form._render_action(name, action, place=place)
                        if self._refresh_button is not None:
                            self.refresh_button = chrome_button('refresh', self._refresh_button, 'refresh', text_of(text.refresh_tooltip), style, lambda _: self.form.refresh(), place)
                        if self._save_button is not None:
                            self.save_button = chrome_button('save', self._save_button, 'save', text_of(text.save_tooltip), style, lambda _: self.form.save(), place)

        if self._description:
            self.description = ui.markdown(self._description)

        self.form.render()
        self._rendered = True
        return self
