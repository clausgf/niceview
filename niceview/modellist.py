"""
ModelList: a Pydantic model collection rendered as a Quasar list (ui.list / ui.item),
suitable for touch-based single-column navigation.

DrillDownWrapper (embeddable list <-> detail navigation on top of ModelList) lives
in niceview.drilldown.
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
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments for ModelList: {', '.join(kwargs.keys())}")

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
    def from_json(cls, item_type: type[T], path_name: Path, *, create_if_not_exist: bool = True, **kwargs: Unpack[_ModelListOptionInputs]) -> Self:
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
