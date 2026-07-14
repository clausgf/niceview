"""
ModelList and DrillDownWrapper for mobile-friendly drill-down navigation.

ModelList renders a Pydantic model collection as a Quasar list (ui.list / ui.item),
suitable for touch-based single-column navigation.

DrillDownWrapper is an embeddable (not page-owning) list <-> detail navigation
widget: a title row plus a ui.refreshable body that swaps between a list view
and a per-item detail view. Call render() inside your own ui.page / ui.card /
ui.column, same as any other niceview widget.
"""
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any, Callable, Self, TypeVar, Unpack
import typing_extensions
from pydantic import BaseModel
from nicegui import ui
from nicegui.events import Handler, ClickEventArguments, handle_event

from niceview.dataadapter import CollectionAdapter, ListAdapter, JsonListAdapter, ReactiveAdapter
from niceview.fieldinfo import FieldInfo
from niceview.fields import Fields
from niceview.form import ModelForm
from niceview.util import confirm_dialog

log = logging.getLogger('niceview')

T = TypeVar('T', bound=BaseModel)

DetailRenderer = Callable[[CollectionAdapter, str, Callable[[str], None]], None]
"""(adapter, key, set_key) -> render the detail body for the item at key. Call
set_key(new_key) whenever the key changes -- e.g. from a "Name" input's blur
handler that calls adapter.rename() -- to keep the wrapper's navigation state
in sync; set_key can be called any time, not just synchronously while
render_detail runs. Build your own ModelForm.from_adapter(...) here for full
control over layout — including resolving a concrete pydantic type per item
for heterogeneous collections."""

ListItemRenderer = Callable[[str, Any, Callable[[], None]], None]
"""(key, item, select) -> render one row of the list view. Call select() from
a click handler to navigate to the detail view for this item."""

ListContainerRenderer = Callable[[Callable[[], None]], None]
"""(render_rows) -> create the container element (e.g. ui.column()) and call
render_rows() inside it. Keep the container via `as container:` to apply
container-level behavior afterward, e.g. container.make_sortable(...). Only
used when render_list_item is also set -- the default ModelList-backed list
view has its own container (a ui.list)."""

_SLIDE_CSS = '''
    @keyframes niceview-slide-in-right { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    @keyframes niceview-slide-in-left  { from { transform: translateX(-100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
    .niceview-slide-in-right { animation: niceview-slide-in-right 0.2s ease-out; }
    .niceview-slide-in-left  { animation: niceview-slide-in-left  0.2s ease-out; }
'''
ui.add_css(_SLIDE_CSS, shared=True)


def _slide_class(direction: str) -> str:
    return 'niceview-slide-in-left' if direction == 'left' else 'niceview-slide-in-right'


@dataclass(kw_only=True, slots=True)
class ListItemSelectEventArguments(ClickEventArguments):
    row_key: str
    item: Any


class _ModelListOptionInputs(typing_extensions.TypedDict, total=False):
    """Keyword options for ModelList and its factory methods."""
    include: list[str] | str
    exclude: list[str] | str
    field_infos: dict[str, FieldInfo]
    profile: str | None
    """Named field layout profile from Meta.profiles (e.g. 'summary', 'detail')."""
    title_field: str | None
    subtitle_fields: list[str] | None


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
    widget: ui.list | None

    def __init__(self, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_ModelListOptionInputs]) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {type(item_type)}")

        self._fields = Fields(item_type, kwargs.pop('include', '__all__'),
                              kwargs.pop('exclude', ''), kwargs.pop('field_infos', {}),
                              profile=kwargs.pop('profile', None))
        self._data = adapter
        self._select_handlers = []
        self._auto_update_registered = False
        self.widget = None

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
        with ui.list().props('dense separator') as self.widget:
            self._render_items()

        if not self._auto_update_registered and isinstance(self._data, ReactiveAdapter):
            def _refresh() -> None:
                self.update_rows()
            self._data.on_change(_refresh)
            self._auto_update_registered = True

        return self


class _DrillDownWrapperOptionInputs(typing_extensions.TypedDict, total=False):
    """Keyword options for DrillDownWrapper and its factory methods."""
    list_title: str
    item_title_field: str | None
    item_subtitle_fields: list[str] | None
    add_button: str | None
    delete_button: str | None
    on_add: Callable[[], None] | None
    on_back: Callable[[], None] | None
    render_list_item: ListItemRenderer | None
    render_list_container: ListContainerRenderer | None
    render_detail: DetailRenderer | None
    # ModelList options forwarded when render_list_item is not set:
    include: list[str] | str
    exclude: list[str] | str
    field_infos: dict[str, FieldInfo]
    profile: str | None


class DrillDownWrapper:
    """
    Embeddable list <-> detail navigation. render() draws a title row (Add in
    list view; Back + item title + Delete in detail view) plus a body that
    swaps between a list view and a per-item detail view, with a slide
    animation on every swap. No NiceGUI page/route of its own — call it inside
    your own ui.page / ui.card / ui.column, same as any other niceview widget.

    Default rendering (both overridable):
      - list view:   ModelList-style rows (title/subtitle from field values)
      - detail view: an autosaving ModelForm.from_adapter(item_type, adapter, key)

    Override render_list_item / render_detail for custom layout, heterogeneous
    item types (resolve the concrete pydantic type per item inside
    render_detail), or non-form content — e.g. rendering a nested
    DrillDownWrapper for a DirectoryAdapter's files. See README.

    After render(), the title row elements are exposed for further styling --
    built once and updated (text/visibility only) rather than recreated on
    every list<->detail navigation, so styling applied here is not lost:
        wrapper.title_row     → ui.row | None
        wrapper.title         → ui.label | None (list title, or the current item's title in detail view)
        wrapper.back_button   → ui.button | None (visible in detail always; in list only if on_back= is set)
        wrapper.add_button    → ui.button | None (visible in list view; None entirely if add_button=None)
        wrapper.delete_button → ui.button | None (visible in detail view; None entirely if delete_button=None)
    The body (list/detail content) is not exposed: unlike the title row, it is genuinely
    torn down and rebuilt on every navigation (list and detail are structurally different
    content, and the swap is where the slide animation lives), so any styling applied to it
    would be silently lost on the next navigation.

    Usage:
        wrapper = DrillDownWrapper.from_list(User, items, list_title='Users')
        wrapper.render()
    """
    _item_type: type[BaseModel]
    _adapter: CollectionAdapter
    _list_title: str
    _item_title_field: str | None
    _item_subtitle_fields: list[str] | None
    _render_list_item: ListItemRenderer | None
    _render_list_container: ListContainerRenderer | None
    _render_detail: DetailRenderer | None
    _on_add: Callable[[], None] | None
    _on_back: Callable[[], None] | None
    _add_button: str | None
    _delete_button: str | None
    _list_kwargs: dict[str, Any]
    _state: dict[str, Any]
    _auto_update_registered: bool

    # Exposed NiceGUI elements: built once in render() and updated (not recreated) on every
    # list<->detail navigation, so styling applied after render() stays put. The body itself
    # (list/detail content) is not exposed -- see _body()'s docstring comment.
    title_row: ui.row | None
    title: ui.label | None
    back_button: ui.button | None
    add_button: ui.button | None
    delete_button: ui.button | None

    def __init__(self, item_type: type[BaseModel], adapter: CollectionAdapter, **kwargs: Unpack[_DrillDownWrapperOptionInputs]) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {type(item_type)}")
        self._item_type = item_type
        self._adapter = adapter
        self._list_title = kwargs.pop('list_title', item_type.__name__ + ' List')
        self._item_title_field = kwargs.pop('item_title_field', None)
        self._item_subtitle_fields = kwargs.pop('item_subtitle_fields', None)
        self._render_list_item = kwargs.pop('render_list_item', None)
        self._render_list_container = kwargs.pop('render_list_container', None)
        self._render_detail = kwargs.pop('render_detail', None)
        self._on_add = kwargs.pop('on_add', None)
        self._on_back = kwargs.pop('on_back', None)
        self._add_button = kwargs.pop('add_button', '')
        self._delete_button = kwargs.pop('delete_button', '')
        self._list_kwargs = dict(kwargs)  # remainder forwarded to ModelList (include, exclude, ...) when render_list_item is unset
        self._state = {'view': 'list', 'key': None, 'direction': 'right'}
        self._auto_update_registered = False

        self.title_row = None
        self.title = None
        self.back_button = None
        self.add_button = None
        self.delete_button = None

        # Resolve the display title field once so the detail title row is consistent
        if self._item_title_field is None:
            fields = Fields(
                item_type,
                self._list_kwargs.get('include', '__all__'),
                self._list_kwargs.get('exclude', ''),
                self._list_kwargs.get('field_infos', {}),
                profile=self._list_kwargs.get('profile', None),
            )
            for name in fields:
                if not fields[name].hidden:
                    self._item_title_field = name
                    break

    # --- factory methods ---------------------------------------------------

    @classmethod
    def from_list(cls, item_type: type[T], items: list[T], **kwargs: Unpack[_DrillDownWrapperOptionInputs]) -> Self:
        """Create a DrillDownWrapper backed by an in-memory list."""
        return cls(item_type, ListAdapter(item_type, items), **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_adapter(cls, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_DrillDownWrapperOptionInputs]) -> Self:
        """Create a DrillDownWrapper from any CollectionAdapter."""
        return cls(item_type, adapter, **kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_json(cls, item_type: type[T], path_name: Path, create_if_not_exist: bool = True, **kwargs: Unpack[_DrillDownWrapperOptionInputs]) -> Self:
        """Create a DrillDownWrapper backed by a JSON file."""
        adapter = JsonListAdapter(item_type, path_name, create_if_not_exist=create_if_not_exist)
        return cls(item_type, adapter, **kwargs)  # type: ignore[arg-type]

    @property
    def adapter(self) -> CollectionAdapter:
        """The backing data adapter."""
        return self._adapter

    # --- navigation ----------------------------------------------------------

    def open(self, key: str) -> Self:
        """Navigate to the detail view for key — e.g. from a custom on_add handler."""
        self._state.update(view='detail', key=key, direction='right')
        self._update_title_row()
        self._body.refresh()
        return self

    def _back(self) -> None:
        self._state.update(view='list', key=None, direction='left')
        self._update_title_row()
        self._body.refresh()

    def _select(self, key: str) -> None:
        self.open(key)

    def _make_select(self, key: str) -> Callable[[], None]:
        return lambda: self._select(key)

    def _on_adapter_change(self) -> None:
        self._body.refresh()

    # --- title row -----------------------------------------------------------

    def _item_title(self, item: Any) -> str:
        return str(getattr(item, self._item_title_field, '')) if self._item_title_field else str(item)

    def _detail_title(self) -> str:
        key = self._state['key']
        if key is None:
            return ''
        try:
            return self._item_title(self._adapter.read(key))
        except (KeyError, ValueError):
            return key

    def _handle_back_click(self) -> None:
        if self._state['view'] == 'detail':
            self._back()
        elif self._on_back is not None:
            self._on_back()

    def _build_title_row(self) -> None:
        # Built once (unlike _body) and updated in place by _update_title_row(): its structure
        # barely changes between list/detail -- just text and which buttons are visible -- so
        # keeping it persistent lets callers style it once after render() instead of every
        # element being wiped out on each list<->detail navigation.
        with ui.row().classes('w-full items-center gap-2') as self.title_row:
            self.back_button = ui.button(icon='arrow_back').props('round dense flat').on_click(self._handle_back_click)
            self.title = ui.label('').classes('text-h6 grow')
            if self._add_button is not None:
                self.add_button = ui.button(self._add_button, icon='add').props('round dense flat color=primary').on_click(self._handle_add)
            if self._delete_button is not None:
                self.delete_button = ui.button(self._delete_button, icon='delete').props('round dense flat color=negative').on_click(self._handle_delete)

    def _update_title_row(self) -> None:
        assert self.back_button is not None and self.title is not None
        is_detail = self._state['view'] == 'detail'
        self.back_button.set_visibility(is_detail or self._on_back is not None)
        self.title.set_text(self._detail_title() if is_detail else self._list_title)
        if self.add_button is not None:
            self.add_button.set_visibility(not is_detail)
        if self.delete_button is not None:
            self.delete_button.set_visibility(is_detail)

    # --- body ------------------------------------------------------------------

    @ui.refreshable_method
    def _body(self) -> None:
        # Not exposed for styling: unlike title_row, this container is genuinely torn down
        # and rebuilt on every navigation (list and detail are structurally different content),
        # so any styling applied to it would be silently lost on the next swap.
        with ui.column().classes(f'w-full gap-2 {_slide_class(self._state["direction"])}'):
            if self._state['view'] == 'detail' and self._state['key'] is not None:
                self._render_detail_view(self._state['key'])
            else:
                self._render_list_view()

    def _render_list_view(self) -> None:
        if self._render_list_item is not None:
            items = list(self._adapter.items())
            if not items:
                ui.label('No items yet.').classes('italic')
                return
            render_list_item = self._render_list_item

            def render_rows() -> None:
                for key, item in items:
                    render_list_item(key, item, self._make_select(key))

            if self._render_list_container is not None:
                self._render_list_container(render_rows)
            else:
                render_rows()
            return
        model_list = ModelList(
            self._item_type, self._adapter,
            title_field=self._item_title_field,
            subtitle_fields=self._item_subtitle_fields,
            **self._list_kwargs,
        )
        # _render_list_view() runs again on every DrillDownWrapper._body refresh, creating a
        # fresh ModelList each time. Skip ModelList's own reactive on_change registration --
        # our own registration in render() already re-renders the whole body on adapter changes,
        # and letting each throwaway ModelList instance register too would leak a growing chain
        # of on_change handlers pointing at stale, already-deleted widgets.
        model_list._auto_update_registered = True
        model_list.on_select(lambda e: self.open(e.row_key))
        model_list.render()

    def _default_render_detail(self, adapter: CollectionAdapter, key: str, set_key: Callable[[str], None]) -> None:
        form = ModelForm.from_adapter(self._item_type, adapter, key, autosave=True)
        form.render()
        form.render_nonfield_errors()

    def _set_detail_key(self, new_key: str) -> None:
        if new_key != self._state['key']:
            self._state['key'] = new_key
            self._update_title_row()
            self._body.refresh()

    def _render_detail_view(self, key: str) -> None:
        try:
            self._adapter.read(key)
        except (KeyError, ValueError):
            ui.label(f'Item {key!r} not found.').classes('text-negative')
            return
        renderer = self._render_detail or self._default_render_detail
        renderer(self._adapter, key, self._set_detail_key)

    # --- CRUD actions ------------------------------------------------------

    def _handle_add(self) -> None:
        if self._on_add is not None:
            self._on_add()
            return
        item = self._adapter.create(self._item_type())
        self.open(self._adapter.key_from_item(item))

    async def _handle_delete(self) -> None:
        key = self._state['key']
        if key is None:
            return
        if not await confirm_dialog('Delete', 'Delete this item? This cannot be undone.', ok_label='Delete', ok_color='negative'):
            return
        try:
            self._adapter.delete(key)
        except Exception as e:
            log.error(f'Error deleting item {key!r}: {e}')
            ui.notify(f'Error deleting item: {e}', color='negative')
            return
        ui.notify('Item deleted', color='positive')
        self._back()

    # --- render --------------------------------------------------------------

    def render(self) -> Self:
        """Render the title row and list/detail body into the current NiceGUI context."""
        self._build_title_row()
        self._update_title_row()
        self._body()
        if not self._auto_update_registered and isinstance(self._adapter, ReactiveAdapter):
            self._adapter.on_change(self._on_adapter_change)
            self._auto_update_registered = True
        return self
