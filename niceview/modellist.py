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
from niceview.util import meta_option, resolve_repository
from niceview.fields import Fields
from niceview.style import ChromeStyle, get_chrome_style
from niceview.widgets import format_number, to_widget_value

log = logging.getLogger('niceview')

T = TypeVar('T', bound=BaseModel)


@dataclass(kw_only=True, slots=True)
class ListItemSelectEventArguments(ClickEventArguments):
    """Fired by ModelList.on_select when a row is tapped."""
    row_key: str
    """Key of the tapped row."""
    item: Any
    """The tapped row's item."""


class _ModelListOptionInputs(typing_extensions.TypedDict, total=False):
    """Keyword options for ModelList and its factory methods."""
    include: list[str] | str
    """Fields to show; '__all__' (default) or a list of names."""
    exclude: list[str] | str
    """Fields to hide; combines with include."""
    field_infos: dict[str, FieldInfo]
    """Per-field FieldInfo overrides, by field name."""
    profile: str | None
    """Named field layout profile from Meta.profiles (e.g. 'summary', 'detail'). Defaults to
    Meta.default_profile when omitted."""
    local_tz: str | None
    """Timezone for datetime display (e.g. 'Europe/Berlin'), like ModelForm's."""
    title_field: str | None
    """Field shown as each row's title; the first visible field if omitted."""
    subtitle_fields: list[str] | None
    """Fields shown as each row's subtitle; the next two visible fields if omitted."""
    chrome_style: ChromeStyle | None
    """Look of the list and its rows. Replaces the application-wide default of
    niceview.style.set_chrome_style() wholesale — derive it with get_chrome_style().replace()."""


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

    The look of the list and its rows comes from the chrome style — application-wide via
    niceview.style.set_chrome_style(), or for this list alone via chrome_style=. Styling
    .widget directly is not enough: update_rows() rebuilds every row inside it.
    """
    _fields: Fields
    _data: CollectionAdapter
    _title_field: str | None
    _subtitle_fields: list[str]
    _select_handlers: list[Handler[ListItemSelectEventArguments]]
    _auto_update_registered: bool
    _chrome_style: ChromeStyle | None
    _model_repositories: dict[type[BaseModel] | str, CollectionAdapter]
    _local_tz: str | None
    widget: ui.list | None

    def __init__(self, item_type: type[T], adapter: CollectionAdapter, **kwargs: Unpack[_ModelListOptionInputs]) -> None:
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {type(item_type)}")

        # include/exclude/field_infos fall back to the model's Meta (like ModelForm); profile
        # stays kwargs-only -- Fields() itself resolves Meta.default_profile as its fallback.
        include = meta_option(item_type, kwargs, 'include', '__all__')
        exclude = meta_option(item_type, kwargs, 'exclude', '')
        field_infos = meta_option(item_type, kwargs, 'field_infos', {})
        self._fields = Fields(item_type, include, exclude, field_infos,
                              profile=kwargs.pop('profile', None))
        self._local_tz = meta_option(item_type, kwargs, 'local_tz', None)
        self._data = adapter
        self._select_handlers = []
        self._auto_update_registered = False
        self._chrome_style = kwargs.pop('chrome_style', None)
        self._model_repositories = {}
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

    def _display_value(self, field_name: str, value: Any) -> str:
        """The text shown for a field value: a modelselect key resolves through its repository
        to the referenced item's label; a choice field's stored value resolves to its label
        (static options/literal_options only — an async options= callable can't be awaited
        here); a date/time-family value goes through the same conversion as ModelForm's widgets
        (local_tz included); a checkbox/switch field shows '✓'/'✗'; a ui.number field with any
        of precision/number_format/prefix/suffix set is formatted the same way ui.number itself
        would; a list joins its items with ', ', each resolved the same way; everything else is
        shown via str()."""
        if value is None:
            return ''
        fi = self._fields.get(field_name)
        if fi is None:
            return str(value)
        if fi.widget_type == 'modelselect' and not isinstance(value, BaseModel):
            repo = resolve_repository(self._model_repositories, field_name, fi.item_type)
            if repo is not None:
                try:
                    return str(repo.read(str(value)))
                except (KeyError, ValueError):
                    return str(value)  # stale key — show it rather than nothing
            return str(value)
        if fi.widget_type in ('datetime', 'date', 'time', 'timedelta'):
            return str(to_widget_value(fi, value, local_tz=self._local_tz))
        if fi.widget_type in ('ui.checkbox', 'ui.switch'):
            return '✓' if value else '✗'
        if fi.widget_type == 'ui.number' and (fi.precision is not None or fi.number_format
                                              or fi.prefix or fi.suffix):
            return format_number(fi, value)
        options = fi.options or fi.literal_options
        labels = {str(k): str(v) for k, v in options.items()} if isinstance(options, dict) else None
        if isinstance(value, list):
            return ', '.join(labels.get(str(v), str(v)) if labels else str(v) for v in value)
        if labels is not None:
            return labels.get(str(value), str(value))
        return str(value)

    def _item_title(self, item: Any) -> str:
        if not self._title_field:
            return str(item)
        return self._display_value(self._title_field, getattr(item, self._title_field, None))

    def _item_subtitle(self, item: Any) -> str:
        parts = []
        for field_name in self._subtitle_fields:
            parts.append(self._display_value(field_name, getattr(item, field_name, None)))
        return ' · '.join(parts)

    def with_repositories(self, repositories: 'dict') -> Self:
        """Register repositories for modelselect fields shown as title/subtitle, so a stored key
        displays the referenced item's label. Keys are a field name (preferred) or the related
        model type — the same form the other components accept."""
        self._model_repositories = {**self._model_repositories, **repositories}  # merge; new wins
        if self.widget is not None:
            self.update_rows()
        return self

    def _render_items(self) -> None:
        style = self._chrome_style or get_chrome_style()
        for item in self._data:
            key = self._data.key_from_item(item)
            subtitle = self._item_subtitle(item)
            with ui.item(on_click=lambda k=key, i=item: self._handle_select(k, i)).classes(style.list_item_classes):
                with ui.item_section():
                    ui.item_label(self._item_title(item)).props(style.list_title_props)
                    if subtitle:
                        ui.item_label(subtitle).props(style.list_subtitle_props)
                if style.list_chevron_icon is not None:
                    with ui.item_section().props('side'):
                        ui.icon(style.list_chevron_icon).classes(style.list_chevron_classes)

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
        style = self._chrome_style or get_chrome_style()
        with ui.list().props(style.list_props).classes('w-full') as self.widget:
            self._render_items()

        if not self._auto_update_registered and isinstance(self._data, ReactiveAdapter):
            def _refresh() -> None:
                self.update_rows()
            self._data.on_change(_refresh)
            self._auto_update_registered = True

        return self
