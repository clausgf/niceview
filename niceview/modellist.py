"""
ModelList and DrillDownWrapper for mobile-friendly drill-down navigation.

ModelList renders a Pydantic model collection as a Quasar list (ui.list / ui.item),
suitable for touch-based single-column navigation.

DrillDownWrapper registers two NiceGUI pages — a list page and a per-item detail page —
and wires up the navigation between them.
"""
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Self, TypeVar, Unpack
import typing_extensions
from pydantic import BaseModel
from nicegui import ui
from nicegui.events import Handler, ClickEventArguments, handle_event

from niceview.dataadapter import CollectionAdapter, ListAdapter, JsonListAdapter, ReactiveAdapter
from niceview.fieldinfo import FieldInfo
from niceview.fields import Fields
from niceview.modelform import ModelForm
from niceview.modeledit import EditFormWrapper
from niceview.util import submit_dialog

log = logging.getLogger('niceview')

T = TypeVar('T', bound=BaseModel)


@dataclass(kw_only=True, slots=True)
class ListItemSelectEventArguments(ClickEventArguments):
    row_key: str
    item: Any


class _ModelListOptionInputs(typing_extensions.TypedDict, total=False):
    """Keyword options for ModelList and its factory methods."""
    include: list[str] | str
    exclude: list[str] | str
    field_infos: dict[str, FieldInfo]
    title_field: str | None
    subtitle_fields: list[str] | None
    classes: str


class ModelList:
    """
    Renders a Pydantic model collection as a Quasar list (ui.list / ui.item).
    Each item shows a title line and an optional subtitle, with a chevron indicating drill-down.

    The first visible field is used as the title; the next two as subtitle by default.
    Override with title_field= and subtitle_fields=.

    Create via factory methods:
      ModelList.from_list(Type, items)       — in-memory list
      ModelList.from_json(Type, path)        — JSON file
      ModelList.from_adapter(Type, adapter)  — any CollectionAdapter

    After render(), the NiceGUI list element is available as .widget.
    Call update_rows() to refresh from the adapter.
    """
    _fields: Fields
    _data: CollectionAdapter
    _title_field: str | None
    _subtitle_fields: list[str]
    _select_handlers: list[Handler[ListItemSelectEventArguments]]
    _auto_update_registered: bool
    classes: str
    widget: ui.list | None

    def __init__(self, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_ModelListOptionInputs]) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {type(item_type)}")

        self._fields = Fields(item_type, kwargs.pop('include', '__all__'),
                              kwargs.pop('exclude', ''), kwargs.pop('field_infos', {}))
        self._data = adapter
        self._select_handlers = []
        self._auto_update_registered = False
        self.widget = None
        self.classes = kwargs.pop('classes', '')

        visible = [n for n in self._fields if not self._fields[n].hidden]
        title_field = kwargs.pop('title_field', None)
        subtitle_fields = kwargs.pop('subtitle_fields', None)
        self._title_field = title_field if title_field is not None else (visible[0] if visible else None)
        self._subtitle_fields = subtitle_fields if subtitle_fields is not None else visible[1:3]

    # --- factory methods ---------------------------------------------------

    @classmethod
    def from_list(cls, item_type: type[T], items: list[T], **kwargs: Unpack[_ModelListOptionInputs]) -> Self:
        """Create a ModelList backed by an in-memory list."""
        return cls(item_type, ListAdapter(item_type, items), **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_adapter(cls, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_ModelListOptionInputs]) -> Self:
        """Create a ModelList from any CollectionAdapter."""
        return cls(item_type, adapter, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_json(cls, item_type: type[T], path_name: Path, create_if_not_exist: bool = True, **kwargs: Unpack[_ModelListOptionInputs]) -> Self:
        """Create a ModelList backed by a JSON file."""
        adapter = JsonListAdapter(item_type, path_name, create_if_not_exist=create_if_not_exist)
        return cls(item_type, adapter, **kwargs)  # type: ignore[arg-type]

    @property
    def adapter(self) -> CollectionAdapter:
        """The backing data adapter."""
        return self._data

    # --- event handler configuration --------------------------------------

    def on_select(self, callback: Handler[ListItemSelectEventArguments]) -> Self:
        """Add a callback invoked when the user taps an item."""
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._select_handlers.append(callback)
        return self

    def _handle_select(self, row_key: str, item: Any) -> None:
        widget = self.widget
        lse = ListItemSelectEventArguments(
            sender=widget,  # type: ignore[arg-type]
            client=widget.client if widget else None,  # type: ignore[arg-type]
            row_key=row_key,
            item=item,
        )
        for handler in self._select_handlers:
            handle_event(handler, lse)

    # --- data and rendering -----------------------------------------------

    def _item_title(self, item: Any) -> str:
        return str(getattr(item, self._title_field, '')) if self._title_field else str(item)

    def _item_subtitle(self, item: Any) -> str:
        parts = []
        for field_name in self._subtitle_fields:
            fi = self._fields.get(field_name)
            label = fi.label if fi else field_name
            parts.append(f'{label}: {getattr(item, field_name, "")}')
        return ' · '.join(parts)

    def _render_items(self) -> None:
        for item in self._data:
            key = self._data.key_from_item(item)
            subtitle = self._item_subtitle(item)
            with ui.item(on_click=lambda k=key, i=item: self._handle_select(k, i)).classes('cursor-pointer'):
                with ui.item_section():
                    ui.item_label(self._item_title(item))
                    if subtitle:
                        ui.item_label(subtitle).props('caption')
                with ui.item_section().props('side'):
                    ui.icon('chevron_right').classes('text-grey')

    def update_rows(self) -> Self:
        """Refresh the displayed list from the adapter."""
        if self.widget is None:
            return self
        self.widget.clear()
        with self.widget:
            self._render_items()
        return self

    def render(self) -> Self:
        """Render the list widget into the current NiceGUI context."""
        with ui.list().props('dense separator').classes(self.classes) as self.widget:
            self._render_items()

        if not self._auto_update_registered and isinstance(self._data, ReactiveAdapter):
            self._data.on_change(lambda: self.update_rows())
            self._auto_update_registered = True

        return self


class DrillDownWrapper:
    """
    Registers two NiceGUI pages for mobile-friendly drill-down navigation:
      - List page  (base_path)        : ModelList with Add button in the header
      - Detail page (base_path/{key}) : ModelForm with Back and Delete buttons in the header

    Call register(base_path) during app setup — before ui.run() — to wire up the pages.

    Usage:
        wrapper = DrillDownWrapper.from_list(User, items, title='Users')
        wrapper.register('/users')
        ui.run()

    On desktop the same pages work with a split-panel layout if desired; the page structure
    is intentionally separate from the rendering so a future responsive layout can be dropped
    in without changing the public API.
    """
    _item_type: type[BaseModel]
    _adapter: CollectionAdapter
    _title: str
    _title_field: str | None
    _subtitle_fields: list[str] | None
    _add_button: str | None
    _delete_button: str | None
    _list_kwargs: dict[str, Any]

    def __init__(self, item_type: type[T], adapter: CollectionAdapter, **kwargs: Any) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {type(item_type)}")
        self._item_type = item_type
        self._adapter = adapter
        self._title = kwargs.pop('title', item_type.__name__ + ' List')
        self._title_field = kwargs.pop('title_field', None)
        self._subtitle_fields = kwargs.pop('subtitle_fields', None)
        self._add_button = kwargs.pop('add_button', '')
        self._delete_button = kwargs.pop('delete_button', '')
        self._list_kwargs = kwargs  # remainder forwarded to ModelList (include, exclude, ...)

        # Resolve the display title field once so the detail page header is consistent
        if self._title_field is None:
            fields = Fields(
                item_type,
                self._list_kwargs.get('include', '__all__'),
                self._list_kwargs.get('exclude', ''),
                self._list_kwargs.get('field_infos', {}),
            )
            for name in fields:
                if not fields[name].hidden:
                    self._title_field = name
                    break

    # --- factory methods ---------------------------------------------------

    @classmethod
    def from_list(cls, item_type: type[T], items: list[T], **kwargs: Any) -> Self:
        """Create a DrillDownWrapper backed by an in-memory list."""
        return cls(item_type, ListAdapter(item_type, items), **kwargs)

    @classmethod
    def from_adapter(cls, item_type: type[T], adapter: CollectionAdapter, **kwargs: Any) -> Self:
        """Create a DrillDownWrapper from any CollectionAdapter."""
        return cls(item_type, adapter, **kwargs)

    @classmethod
    def from_json(cls, item_type: type[T], path_name: Path, create_if_not_exist: bool = True, **kwargs: Any) -> Self:
        """Create a DrillDownWrapper backed by a JSON file."""
        adapter = JsonListAdapter(item_type, path_name, create_if_not_exist=create_if_not_exist)
        return cls(item_type, adapter, **kwargs)

    # --- page registration -------------------------------------------------

    def register(self, base_path: str) -> Self:
        """
        Register list and detail NiceGUI pages at base_path and base_path/{key}.
        Must be called before ui.run(). Multiple wrappers can be registered at different paths.
        """
        wrapper = self

        @ui.page(base_path)
        def list_page():
            wrapper._render_list_page(base_path)

        @ui.page(f'{base_path}/{{key}}')
        def detail_page(key: str):
            wrapper._render_detail_page(base_path, key)

        return self

    # --- page rendering ----------------------------------------------------

    def _item_title(self, item: Any) -> str:
        return str(getattr(item, self._title_field, '')) if self._title_field else str(item)

    def _render_list_page(self, base_path: str) -> None:
        async def on_add_clicked(_: Any) -> None:
            await self._open_create_dialog(base_path)

        with ui.header().classes('items-center'):
            ui.label(self._title).classes('text-h6 grow')
            if self._add_button is not None:
                ui.button(self._add_button, icon='add').props('flat color=white').on_click(on_add_clicked)

        with ui.row().classes('w-full flex-wrap'):
            # List panel: full width on mobile, left third on desktop
            with ui.column().classes('col-12 col-md-4 q-pa-none'):
                model_list = ModelList(
                    self._item_type, self._adapter,
                    title_field=self._title_field,
                    subtitle_fields=self._subtitle_fields,
                    **self._list_kwargs,
                )
                model_list.on_select(lambda e: ui.navigate.to(f'{base_path}/{e.row_key}'))
                model_list.render()
            # Placeholder panel: shown on desktop only, right two thirds
            with ui.column().classes('col-8 gt-sm items-center justify-center q-pa-xl'):
                ui.icon('touch_app').classes('text-grey-4 text-h2')
                ui.label('Select an item to view details').classes('text-grey q-mt-sm')

    def _render_detail_page(self, base_path: str, key: str) -> None:
        try:
            item = self._adapter.read(key)
        except (KeyError, ValueError):
            with ui.header().classes('items-center'):
                ui.button(icon='arrow_back').props('flat color=white').on_click(lambda _: ui.navigate.back())
                ui.label('Not Found').classes('text-h6')
            ui.label(f'Item {key!r} not found').classes('text-negative q-pa-md')
            return

        async def on_delete_clicked(_: Any) -> None:
            await self._delete_item(base_path, key)

        with ui.header().classes('items-center'):
            # Back button visible on mobile only; desktop shows the list panel next to the form
            ui.button(icon='arrow_back').props('flat color=white').classes('lt-md').on_click(lambda _: ui.navigate.back())
            ui.label(self._item_title(item)).classes('text-h6 grow')
            if self._delete_button is not None:
                ui.button(self._delete_button, icon='delete').props('flat color=white').on_click(on_delete_clicked)

        with ui.row().classes('w-full flex-wrap'):
            # List panel: shown on desktop only, left third
            with ui.column().classes('col-4 gt-sm q-pa-none'):
                model_list = ModelList(
                    self._item_type, self._adapter,
                    title_field=self._title_field,
                    subtitle_fields=self._subtitle_fields,
                    **self._list_kwargs,
                )
                model_list.on_select(lambda e: ui.navigate.to(f'{base_path}/{e.row_key}'))
                model_list.render()
            # Form panel: full width on mobile, right two thirds on desktop
            with ui.column().classes('col-12 col-md-8'):
                with ui.card().classes('w-full'):
                    EditFormWrapper.from_adapter(self._item_type, self._adapter, key)

    # --- CRUD actions ------------------------------------------------------

    async def _open_create_dialog(self, base_path: str) -> None:
        """Open a modal dialog to create a new item; navigate to the list on success."""
        item = self._item_type()
        form = ModelForm.from_item(item)

        def confirm() -> None:
            if form.has_validation_errors:
                ui.notify('Cannot save: validation errors present', color='negative')
                return
            # Flush any pending widget values into the validated item (guards against
            # the blur/click race where a field's blur event hasn't arrived yet).
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
                with ui.card_section():
                    with ui.row():
                        ui.space()
                        ui.button('Cancel', on_click=lambda: dialog.submit('cancel'))
                        ui.button('Create', on_click=confirm)

        if 'confirm' == await dialog:
            try:
                self._adapter.create(item)
                ui.notify('Item created', color='positive')
                ui.navigate.to(base_path)
            except Exception as e:
                log.error(f'Error creating item: {e}')
                ui.notify(f'Error creating item: {e}', color='negative')
        dialog.clear()

    async def _delete_item(self, base_path: str, key: str) -> None:
        """Ask for confirmation and delete the item; navigate to the list on success."""
        dialog = submit_dialog('Confirm Deletion', 'Delete this item?')
        result = await dialog
        if result != 'OK':
            return
        try:
            self._adapter.delete(key)
            ui.notify('Item deleted', color='positive')
            ui.navigate.to(base_path)
        except Exception as e:
            log.error(f'Error deleting item {key}: {e}')
            ui.notify(f'Error deleting item: {e}', color='negative')
