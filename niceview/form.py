from dataclasses import dataclass
import datetime
import logging
from typing import Any, Self, TypeVar, Unpack
import typing
from pathlib import Path
from zoneinfo import ZoneInfo
import typing_extensions
from pydantic import BaseModel, TypeAdapter

from nicegui import ui
from nicegui.events import Handler, UiEventArguments, ValueChangeEventArguments, handle_event

from niceview.dataadapter import BoundItem, JsonAdapter, CollectionAdapter, ItemAdapter
from niceview.fieldinfo import FieldInfo
from niceview.fields import Fields

log = logging.getLogger('niceview')

W = TypeVar('W', bound=ui.element)


def _pick_attrs(obj: Any, attrs: list[str]) -> dict[str, Any]:
    """Return a dict of non-None attribute values from obj for the given attribute names."""
    return {k: v for k in attrs if (v := getattr(obj, k)) is not None}


@dataclass(kw_only=True, slots=True)
class FieldChangeEventArguments(UiEventArguments):
    form: 'ModelForm'
    field_name: str
    previous_value: Any
    value: Any


class _ModelFormOptionInputs(typing_extensions.TypedDict, total=False):
    """
    Kwarg Options for the ModelForm class.
    Chrome (title, description, save/refresh buttons) belongs to EditFormWrapper.
    """
    include: list[str] | str
    exclude: list[str] | str
    field_infos: dict[str, FieldInfo]
    profile: str | None
    """Named field layout profile from Meta.profiles (e.g. 'summary', 'detail')."""

    autosave: bool
    """Whether to automatically save the form on field change. Defaults to False (OFF)."""

    local_tz: str | None
    """Local timezone name for datetime display (e.g. 'Europe/Berlin'). Defaults to None (system local timezone)."""

    on_change: Handler[FieldChangeEventArguments]
    """Callback to execute when value changes. To reduce the number of change events, fields like ui.input or ui.number also have to loose focus (blur)."""


class ModelForm():
    """
    Renders a Pydantic model as an editable form (fields only — no chrome).
    Use EditFormWrapper to add a title, description, and action buttons.

    Create via factory methods:
      ModelForm.from_item(instance)              — in-memory item
      ModelForm.from_json(Type, path)            — JSON file, auto-saves
      ModelForm.from_adapter(Type, adapter, key) — any CollectionAdapter

    Configuration options are accepted as keyword arguments or via the model's
    Meta class (kwargs take priority).
    """
    _item_type: type[BaseModel]
    _item_adapter: ItemAdapter | None
    _model_repositories: dict[type[BaseModel], CollectionAdapter]
    _change_handlers: list[Handler[FieldChangeEventArguments]]

    _fields: Fields
    _current_item: BaseModel | None
    _validated_item: BaseModel | None
    _validation_error_messages: dict[str, str]
    _nonfield_validation_errors: list[str]
    _nonfield_error_element: ui.label | None
    widgets: dict[str, Any]

    autosave: bool
    local_tz: str | None

    def __init__(self, item_type: type[BaseModel], **kwargs: Unpack[_ModelFormOptionInputs]) -> None:
        """
        Create a ModelForm for the given Pydantic model type.
        Prefer the factory methods (from_item, from_json, from_adapter) over
        calling the constructor directly.
        """

        def _get_param(param: str, default: Any) -> Any:
            """Get a parameter from (in descending priority) kwargs, Meta class or default value."""
            meta = getattr(self._item_type, 'Meta', None)
            value = getattr(meta, param, default) if meta else default
            value = kwargs.pop(param, value)  # type: ignore[misc]  # dynamic TypedDict key
            return value

        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")

        self._item_type = item_type
        self._item_adapter = None
        self._model_repositories: dict[type[BaseModel], CollectionAdapter] = {}
        self._change_handlers: list[Handler[FieldChangeEventArguments]] = []

        include = _get_param('include', '__all__')
        exclude = _get_param('exclude', '')
        field_infos = _get_param('field_infos', {})
        profile = kwargs.pop('profile', None)  # type: ignore[misc]
        self._fields = Fields(item_type, include, exclude, field_infos, profile=profile)
        self._current_item = None
        self._validated_item = None
        self._validation_error_messages = {}
        self._nonfield_validation_errors = []
        self._nonfield_error_element = None
        self.widgets = {}

        self.autosave = _get_param('autosave', False)
        self.local_tz = _get_param('local_tz', None)

        if on_change_callback := kwargs.pop('on_change', None):
            self.on_change(on_change_callback)

        if len(kwargs) > 0:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(kwargs.keys())}")

    # --- factory methods ---------------------------------------------------

    @typing.overload
    @classmethod
    def from_item(cls, item: BaseModel, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self: ...
    @typing.overload
    @classmethod
    def from_item(cls, item_type: type[BaseModel], item: BaseModel, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self: ...
    @classmethod
    def from_item(cls, item_type_or_item: 'type[BaseModel] | BaseModel', item: 'BaseModel | None' = None, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm editing an in-memory item (no persistence).

        The form modifies the item in-place; form.item returns the same object.
        External changes to the item's attributes are not reflected in the widgets
        automatically — assign form.item = updated_item to push new values to the UI.

        Two call forms:
          from_item(instance)       — item_type inferred from instance
          from_item(Type, instance) — explicit type (e.g. for subclasses)
        """
        if item is None:
            if not isinstance(item_type_or_item, BaseModel):
                raise TypeError(f"item_type_or_item must be a BaseModel instance, got {type(item_type_or_item)}")
            item = item_type_or_item
            item_type = type(item)
        else:
            item_type = item_type_or_item  # type: ignore[assignment]
            if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
                raise TypeError(f"item_type_or_item must be a subclass of BaseModel, got {item_type}")
            if not isinstance(item, BaseModel):
                raise TypeError(f"item must be a BaseModel instance, got {type(item)}")
        ret = cls(item_type, **kwargs)
        ret._set_item(item)
        return ret

    @classmethod
    def from_adapter(cls, item_type: type[BaseModel], adapter: CollectionAdapter, key: str, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm bound to one item in a CollectionAdapter (via BoundItem).
        Calls save() to persist changes; calls refresh() to re-read from the backend.
        """
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")
        instance = cls(item_type, **kwargs)
        instance.load(BoundItem(adapter, key))
        return instance

    @classmethod
    def from_json(cls, item_type: type[BaseModel], json_path: Path, create_if_not_exist: bool = True, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm bound to a single-item JSON file.
        The file is created with default values if it does not exist.
        Calls save() to persist changes; calls refresh() to re-read from disk.
        """
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")
        instance = cls(item_type, **kwargs)
        instance.load(JsonAdapter(item_type, json_path, create_if_not_exist=create_if_not_exist))
        return instance

    # --- item and form state management ------------------------------------

    @property
    def item(self) -> BaseModel:
        """
        Get the current (validated) item of the form.
        This is the item that is currently being edited.
        """
        if self._validated_item is None:
            raise ValueError("No item set. Use from_item(), from_json(), from_adapter(), or load() first.")
        return self._validated_item

    @item.setter
    def item(self, value: BaseModel) -> None:
        """
        Replace the displayed item. Only valid for unbound forms (from_item).
        For adapter-bound forms use load() to navigate.
        """
        if self.adapter_bound:
            raise ValueError(
                "Cannot set item directly on an adapter-bound form. Use load() to navigate."
            )
        if not isinstance(value, BaseModel):
            raise TypeError(f"item must be a BaseModel instance, got {type(value)}")
        self._set_item(value)

    def _set_item(self, value: BaseModel) -> None:
        """Internal item assignment — bypasses the adapter-bound guard."""
        self._validated_item = value
        self._current_item = value.model_copy()
        self._validate()
        self._push_item_to_widgets()

    # --- data adapter interaction ------------------------------------------

    @typing.overload
    def load(self, adapter: ItemAdapter) -> Self: ...
    @typing.overload
    def load(self, adapter: CollectionAdapter, key: str) -> Self: ...
    def load(self, adapter: 'ItemAdapter | CollectionAdapter', key: str | None = None) -> Self:
        """
        Bind the form to an adapter and load the item.

        Two call forms:
          load(item_adapter)       — any ItemAdapter (e.g. BoundItem, JsonAdapter)
          load(collection, key)    — convenience: wraps in BoundItem internally

        Use this for master-detail navigation (switching the displayed item at runtime).
        """
        item_adapter: ItemAdapter = BoundItem(adapter, key) if key is not None else adapter  # type: ignore[arg-type]
        self._item_adapter = item_adapter
        item = item_adapter.read()
        if not isinstance(item, BaseModel):
            raise TypeError(f"item must be a BaseModel instance, got {type(item)}")
        self._set_item(item)
        return self

    @property
    def adapter_bound(self) -> bool:
        """True if the form is bound to a data adapter (save/refresh are available)."""
        return self._item_adapter is not None

    def refresh(self) -> None:
        """Reload the item from the adapter, discarding any unsaved edits."""
        if not self.adapter_bound:
            raise ValueError("No adapter set. Use from_adapter(), from_json(), or load() first.")
        self.load(self._item_adapter)  # type: ignore[arg-type]
        ui.notify('Form refreshed', color='positive')

    def save(self) -> None:
        """Persist the current item to the adapter. No-op if validation errors are present."""
        if not self.adapter_bound:
            raise ValueError("No adapter set. Use from_adapter(), from_json(), or load() first.")

        if self.has_validation_errors:
            ui.notify('Cannot save form: validation errors present', color='negative')
            return

        updated = self._item_adapter.save(self.item)
        if updated is not None and updated is not self._validated_item:
            self._validated_item = updated
            self._current_item = updated.model_copy()
        ui.notify('Form saved', color='positive')

    # --- widget management -------------------------------------------------

    @typing.overload
    def w(self, field_name: str) -> ui.element: ...
    @typing.overload
    def w(self, field_name: str, widget_type: type[W]) -> W: ...
    def w(self, field_name: str, widget_type: 'type[W] | None' = None) -> 'ui.element | W':
        """
        Return the rendered widget for a field, with optional type narrowing.

          form.w('name')               # → ui.element
          form.w('name', ui.input)     # → ui.input  (typed; raises TypeError if mismatch)

        Raises KeyError if the field has no widget (e.g. not yet rendered or excluded).
        Raises TypeError if the widget exists but is not an instance of widget_type.
        """
        try:
            widget = self.widgets[field_name]
        except KeyError:
            raise KeyError(f"No widget for field '{field_name}'. "
                           "Check that the form is rendered and the field is not excluded.")
        if widget_type is not None and not isinstance(widget, widget_type):
            raise TypeError(
                f"Widget for '{field_name}' is {type(widget).__name__}, not {widget_type.__name__}"
            )
        return widget  # type: ignore[return-value]

    def with_repositories(self, repositories: 'dict[type[BaseModel], CollectionAdapter]') -> Self:
        """
        Provide adapters for modelselect fields (SQLModel relationships rendered as dropdowns).
        Keys are model classes (e.g. Author); values are CollectionAdapters for those models.
        Returns self for chaining.
        """
        if not isinstance(repositories, dict):
            raise TypeError(f"repositories must be a dictionary, got {type(dict)}")
        self._model_repositories = repositories
        return self

    def _push_item_to_widgets(self) -> None:
        """Push current item values into all rendered widgets."""
        for field_name, widget in self.widgets.items():
            widget_type = self._fields[field_name].widget_type
            if widget_type and widget_type != 'editgrid':
                self._from_current_item_to_widget_value(field_name, widget_type, widget)

    def on_change(self, callback: Handler[FieldChangeEventArguments]) -> Self:
        """
        Add a callback to be invoked when the form values change and
        the new values are successfully validated.
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._change_handlers.append(callback)
        return self

    # --- widget rendering helpers ------------------------------------------

    @staticmethod
    def _resolve_options(field_name: str, field_info: FieldInfo, primary_attr: str, fallback_attr: str) -> Any:
        """Resolve options for select/radio/toggle widgets from field_info, calling if callable."""
        raw = getattr(field_info, primary_attr) or getattr(field_info, fallback_attr)
        if not raw:
            raise ValueError(f"Field '{field_name}' has no {primary_attr} (or {fallback_attr}) defined in FieldInfo")
        return raw() if callable(raw) else raw

    def _wire_text_input(self, widget: Any, field_name: str) -> None:
        """Wire a text-input widget: validate on change, commit on blur."""
        widget.on_value_change(lambda vce, fn=field_name: self._handle_validate(fn, vce))
        widget.on('blur', lambda e, fn=field_name: self._handle_blur_event(fn, e))
        widget.validation = lambda value, fn=field_name: self._get_field_error(fn, value)

    def _wire_immediate(self, widget: Any, field_name: str) -> None:
        """Wire an immediate widget: validate and commit on value change."""
        widget.on_value_change(lambda vce, fn=field_name: self._handle_validate_and_change(fn, vce))

    def _apply_widget_field_info(self, widget: Any, field_info: FieldInfo) -> None:
        """Apply disable, tooltip, classes, style, props from field_info to a native NiceGUI widget."""
        if not field_info.editable and hasattr(widget, 'disable') and callable(widget.disable):
            widget.disable()
        if field_info.tooltip and hasattr(widget, 'tooltip') and callable(widget.tooltip):
            widget.tooltip(field_info.tooltip)
        if field_info.classes and hasattr(widget, 'classes') and callable(widget.classes):
            widget.classes(field_info.classes)
        if field_info.style and hasattr(widget, 'style') and callable(widget.style):
            widget.style(field_info.style)
        if field_info.props and hasattr(widget, 'props') and callable(widget.props):
            widget.props(field_info.props)

    # --- widget rendering methods ------------------------------------------

    def _render_select_widget(self, field_name: str, field_info: FieldInfo, kwargs: dict[str, Any], value_widget_type: str = 'ui.select') -> ui.select:
        """Render a select widget. Options come from select_options or literal_options on field_info."""
        kwargs['options'] = self._resolve_options(field_name, field_info, 'select_options', 'literal_options')
        widget = ui.select(**kwargs)
        self._from_current_item_to_widget_value(field_name, value_widget_type, widget)
        self._wire_immediate(widget, field_name)
        widget.validation = lambda value, fn=field_name: self._get_field_error(fn, value)
        return widget

    def _render_radio_widget(self, field_name: str, field_info: FieldInfo) -> ui.radio:
        """Render a radio widget. Options come from radio_options or literal_options on field_info."""
        options = self._resolve_options(field_name, field_info, 'radio_options', 'literal_options')
        widget = ui.radio(options)
        self._from_current_item_to_widget_value(field_name, 'ui.radio', widget)
        self._wire_immediate(widget, field_name)
        return widget

    def _render_toggle_widget(self, field_name: str, field_info: FieldInfo) -> ui.toggle:
        """Render a toggle widget. Options come from toggle_options or literal_options on field_info."""
        options = self._resolve_options(field_name, field_info, 'toggle_options', 'literal_options')
        widget = ui.toggle(options)
        self._from_current_item_to_widget_value(field_name, 'ui.toggle', widget)
        self._wire_immediate(widget, field_name)
        return widget

    def _render_modelselect_widget(self, field_name: str, field_info: FieldInfo, kwargs: dict[str, Any]) -> ui.select:
        """Render a model-backed select widget using a CollectionAdapter from with_repositories()."""
        if not field_info.item_type:
            raise ValueError(f"Field {field_name} is a model select but no item type is specified in FieldInfo or as a pydantic model type")

        if field_info.item_type not in self._model_repositories:
            log.warning(
                f"No repository for '{field_info.item_type.__name__}' — "
                f"rendering '{field_name}' as a disabled placeholder. "
                f"Call with_repositories() to enable this field."
            )
            widget = ui.select(options={}, label=field_info.label or field_name)
            widget.disable()
            return widget  # type: ignore[return-value]

        repo = self._model_repositories[field_info.item_type]
        field_info.select_options = {repo.key_from_item(item): str(item) for item in repo}
        return self._render_select_widget(field_name, field_info, kwargs, value_widget_type='modelselect')

    def _get_fk_info(self, field_name: str) -> tuple[str, Any] | None:
        """
        For SQLModel parents: inspect the SQLAlchemy relationship to find the FK field
        on the child side and the current parent PK value.
        Returns (fk_field_name, parent_pk_value), or None if not determinable or
        if the parent item has no PK yet (new, unpersisted item).
        """
        try:
            from sqlalchemy import inspect as sa_inspect
            mapper = sa_inspect(type(self._validated_item))
            if mapper is None or not hasattr(mapper, 'relationships'):
                return None
            rel = mapper.relationships.get(field_name)
            if rel is None or not rel.synchronize_pairs:
                return None
            local_col, remote_col = rel.synchronize_pairs[0]
            parent_value = getattr(self._validated_item, local_col.key, None)
            if parent_value is None:
                return None  # parent not yet persisted — no valid FK to inject
            return remote_col.key, parent_value
        except Exception:
            return None

    def _render_editgrid_widget(self, field_name: str, field_info: FieldInfo) -> Any:
        # Local imports to avoid circular dependencies (grid/wrapper import form).
        from niceview.wrapper import EditGridWrapper
        from niceview.grid import ModelGrid, TableItemEventArguments
        from niceview.dataadapter import ListAdapter, FilteredAdapter

        def notify_change(e: TableItemEventArguments) -> None:
            if self.autosave:
                self.save()
            fce = FieldChangeEventArguments(
                sender=e.sender,
                client=e.client,
                form=self,
                field_name=field_name,
                previous_value=None,
                value=e.item,
            )
            for handler in self._change_handlers:
                handle_event(handler, fce)

        if not field_info.item_type:
            raise ValueError(f"Field {field_name} is a list but no item type is specified in FieldInfo or as a pydantic model type")

        # If model_repositories has an adapter for the child type and the parent has
        # a valid PK, use a FilteredAdapter so mutations are persisted via the adapter.
        # Otherwise fall back to an in-memory ListAdapter.
        repo = self._model_repositories.get(field_info.item_type)
        data: CollectionAdapter
        if repo is not None:
            fk_info = self._get_fk_info(field_name)
            if fk_info is not None:
                fk_field, parent_value = fk_info
                data = FilteredAdapter(
                    repo,
                    predicate=lambda item, fk=fk_field, val=parent_value: getattr(item, fk, None) == val,
                    defaults={fk_field: parent_value},
                )
            else:
                data = ListAdapter(field_info.item_type, getattr(self._validated_item, field_name))
        else:
            data = ListAdapter(field_info.item_type, getattr(self._validated_item, field_name))

        widget = ModelGrid(field_info.item_type, data)
        if field_info.editable:
            edit_widget = EditGridWrapper(widget, title=field_info.label)
            if self._model_repositories:
                edit_widget.with_repositories(self._model_repositories)
            edit_widget.on_change(notify_change)
            edit_widget.render()
            return edit_widget  # type: ignore[return-value]
        else:
            ui.label(field_info.label).classes('text-h6')
            widget.render()
            return widget  # type: ignore[return-value]

    def _render_widget(self, field_name: str, field_info: FieldInfo) -> Any:
        """Create and wire a widget for the given field, based on its widget_type."""
        if not field_info:
            raise ValueError(f"Field info for {field_name} not found")
        widget_type = field_info.widget_type
        if not widget_type:
            raise ValueError(f"Widget type for field {field_name} not found in field info")

        # For native NiceGUI widgets, disable/tooltip/classes/style/props are applied after
        # creation. Non-native widgets (editgrid) manage their own styling.
        is_native_widget = True
        widget: Any = None

        if widget_type == 'ui.input':
            widget = ui.input(**_pick_attrs(field_info, ['label', 'placeholder', 'password', 'password_toggle_button', 'autocomplete']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'ui.number':
            widget = ui.number(**_pick_attrs(field_info, ['label', 'placeholder', 'min', 'max', 'precision', 'step', 'prefix', 'suffix', 'format']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'ui.textarea':
            widget = ui.textarea(**_pick_attrs(field_info, ['label', 'placeholder']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'ui.checkbox':
            widget = ui.checkbox(text=field_info.label)
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_immediate(widget, field_name)
            # validation display is irrelevant for checkboxes

        elif widget_type == 'ui.switch':
            widget = ui.switch(text=field_info.label)
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_immediate(widget, field_name)
            # validation display is irrelevant for switches

        elif widget_type == 'ui.select':
            widget = self._render_select_widget(field_name, field_info, _pick_attrs(field_info, ['label', 'with_input', 'multiple', 'clearable']))

        elif widget_type == 'ui.radio':
            widget = self._render_radio_widget(field_name, field_info)

        elif widget_type == 'ui.toggle':
            widget = self._render_toggle_widget(field_name, field_info)

        elif widget_type == 'ui.color_input':
            widget = ui.color_input(**_pick_attrs(field_info, ['label', 'placeholder']), preview=field_info.color_preview)
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_immediate(widget, field_name)

        elif widget_type == 'ui.input_chips':
            widget = ui.input_chips(**_pick_attrs(field_info, ['label', 'new_value_mode']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'datetime':
            widget = ui.input(**_pick_attrs(field_info, ['label', 'placeholder'])).props('type=datetime-local').props('step=1')
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'date':
            # Prefer the native HTML date input over NiceGUI/Quasar's date_input because it is
            # more lightweight and has better browser support. Value format is YYYY-MM-DD.
            widget = ui.input(**_pick_attrs(field_info, ['label', 'placeholder'])).props('type=date')
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'time':
            # Same rationale as 'date': prefer the native HTML time input over NiceGUI/Quasar.
            widget = ui.input(**_pick_attrs(field_info, ['label', 'placeholder'])).props('type=time').props('step=1')
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'timedelta':
            widget = ui.input(**_pick_attrs(field_info, ['label', 'placeholder']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_text_input(widget, field_name)

        elif widget_type == 'slider':
            slider_min = field_info.min if field_info.min is not None else 0.0
            slider_max = field_info.max if field_info.max is not None else 100.0
            slider_kwargs: dict[str, Any] = {'min': slider_min, 'max': slider_max}
            if field_info.step is not None:
                slider_kwargs['step'] = field_info.step
            with ui.column().classes('w-full gap-1'):
                if field_info.label:
                    ui.label(field_info.label).classes('text-caption')
                widget = ui.slider(**slider_kwargs).props('label-always')
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_immediate(widget, field_name)

        elif widget_type == 'rating':
            rating_max = int(field_info.max) if field_info.max is not None else 5
            with ui.column().classes('gap-1'):
                if field_info.label:
                    ui.label(field_info.label).classes('text-caption')
                widget = ui.rating(max=rating_max)
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            self._wire_immediate(widget, field_name)

        elif widget_type == 'editgrid':
            widget = self._render_editgrid_widget(field_name, field_info)
            is_native_widget = False

        elif widget_type == 'modelselect':
            widget = self._render_modelselect_widget(field_name, field_info, _pick_attrs(field_info, ['label', 'with_input', 'multiple', 'clearable']))

        if widget is None:
            raise ValueError(f"Invalid widget class: {widget_type}")

        if is_native_widget:
            self._apply_widget_field_info(widget, field_info)

        return widget

    def render(self) -> Self:
        """
        Render the form fields. Use EditFormWrapper for title, description and action buttons.
        """
        self.widgets = {}
        for field_name in self._fields:
            field_info = self._fields[field_name]
            if not field_info:
                raise ValueError(f"Field {field_name} not found in field_infos")
            if field_info.hidden:
                continue
            self.widgets[field_name] = self._render_widget(field_name, field_info)

        self._nonfield_error_element = ui.label('').classes('text-negative w-full')
        self._nonfield_error_element.set_visibility(False)

        return self

    # --- value conversion --------------------------------------------------

    def _from_current_item_to_widget_value(self, field_name: str, widget_type: str, widget: Any) -> None:
        """Push the current item's field value into the widget."""
        value = getattr(self._current_item, field_name)

        if widget_type == 'modelselect':
            item_type = self._fields[field_name].item_type
            assert item_type is not None, f"item_type for field '{field_name}' must not be None"
            repository = self._model_repositories[item_type]
            if not repository:
                raise ValueError(f"Model repository for {item_type.__name__} not found in form's model repositories")
            value = repository.key_from_item(value) if value is not None else None

        elif type(value) is datetime.datetime:
            tz = ZoneInfo(self.local_tz) if self.local_tz else None
            value = value.astimezone(tz).replace(tzinfo=None).isoformat()

        elif widget_type == 'timedelta':
            timedelta_adapter = TypeAdapter(datetime.timedelta)
            value = timedelta_adapter.dump_python(value, mode="json")

        widget.value = value  # type: ignore[attr-defined]

    def _from_widget_value_to_current_item(self, field_name: str) -> None:
        """
        Read the widget value, convert it to the model type, and write it into _current_item.
        Exceptions should be handled by the caller.
        """
        if field_name not in self.widgets:
            raise ValueError(f"Widget for field {field_name} not found")
        widget = self.widgets[field_name]
        widget_type = self._fields[field_name].widget_type
        field_type = self._fields[field_name].field_type
        value = widget.value  # type: ignore[attr-defined]

        if widget_type == 'ui.input' and typing.get_origin(field_type) == list:
            value = [item.strip() for item in value.split(',')]
            item_type = self._fields[field_name].item_type
            if item_type in (int, float, bool, str):
                value = [item_type(item) for item in value]
            else:
                raise ValueError(f"Field '{field_name}' is a list but no allowed item type is specified")

        elif widget_type == 'ui.number':
            if field_type == int:
                value = int(value)
            else:
                value = float(value)

        elif widget_type in ('slider', 'rating'):
            if field_type == int:
                value = int(value) if value is not None else 0
            else:
                value = float(value) if value is not None else 0.0

        elif widget_type == 'ui.input_chips':
            expanded = []
            for v in value:
                if isinstance(v, str) and ',' in v:
                    expanded.extend(item.strip() for item in v.split(','))
                else:
                    expanded.append(v)
            value = expanded

        elif widget_type == 'datetime':
            dt = datetime.datetime.fromisoformat(value)
            tz = ZoneInfo(self.local_tz) if self.local_tz else None
            value = dt.replace(tzinfo=tz).astimezone(datetime.timezone.utc)

        elif widget_type == 'timedelta':
            timedelta_adapter = TypeAdapter(datetime.timedelta)
            value = timedelta_adapter.validate_python(value)

        elif widget_type == 'modelselect':
            item_type = self._fields[field_name].item_type
            assert item_type is not None, f"item_type for field '{field_name}' must not be None"
            repository = self._model_repositories[item_type]
            if not repository:
                raise ValueError(f"Model repository for {item_type.__name__} not found in form's model repositories")
            value = repository.read(value) if value is not None else None
            # Sync FK field (e.g. author -> author_id) so pydantic validation sees the selection.
            # Do NOT also set the relationship attribute: SQLAlchemy would cascade-insert the
            # detached related instance, violating UNIQUE constraints on the related table.
            fk_field = f'{field_name}_id'
            if fk_field in getattr(type(self._current_item), 'model_fields', {}):
                if value is not None:
                    key_str = repository.key_from_item(value)
                    fk_type = type(self._current_item).model_fields[fk_field].annotation
                    fk_val = TypeAdapter(fk_type).validate_python(key_str)
                else:
                    fk_val = None
                setattr(self._current_item, fk_field, fk_val)
                return  # FK synced; skip setting the relationship object

        setattr(self._current_item, field_name, value)

    # --- validation and event handling ------------------------------------

    def _get_field_error(self, field_name: str, value: Any) -> str | None:
        """NiceGUI validation callback: return the current error message for field_name, or None."""
        return self._validation_error_messages.get(field_name, None)

    def _validate(self) -> None:
        if self._current_item is None:
            return
        field_errors, nonfield_errors = self._fields.validation_errors(self._current_item.model_dump())
        self._validation_error_messages = field_errors
        self._nonfield_validation_errors = nonfield_errors

        if self._nonfield_error_element is not None:
            if nonfield_errors:
                self._nonfield_error_element.set_text(' | '.join(nonfield_errors))
                self._nonfield_error_element.set_visibility(True)
            else:
                self._nonfield_error_element.set_visibility(False)

        for widget in self.widgets.values():
            if hasattr(widget, 'validate') and callable(widget.validate):
                widget.validate()

    @property
    def has_validation_errors(self) -> bool:
        """True if any field-level or model-level validation errors are present."""
        return bool(self._validation_error_messages) or bool(self._nonfield_validation_errors)

    @property
    def validation_errors(self) -> dict[str, str]:
        """Field-level validation errors as {field_name: error_message}. Empty dict when valid."""
        return dict(self._validation_error_messages)

    @property
    def nonfield_validation_errors(self) -> list[str]:
        """Model-level (cross-field) validation errors. Empty list when valid."""
        return list(self._nonfield_validation_errors)

    def _handle_blur_event(self, field_name: str, event: Any) -> None:
        old = getattr(self._current_item, field_name, None) if self._current_item else None
        vce = ValueChangeEventArguments(
            sender=event.sender, client=event.client,
            value=event.sender.value,  # type: ignore[attr-defined]
            previous_value=old,
        )
        self._handle_value_change(field_name, vce)

    def _handle_validate(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        old_value = getattr(self._current_item, field_name)
        new_value = value_change_event.sender.value  # type: ignore[attr-defined]

        if old_value != new_value:
            error_msg = None
            try:
                self._from_widget_value_to_current_item(field_name)
            except Exception:
                error_msg = "Error interpreting widget value"

            self._validate()

            # reflect conversion errors in the validation error messages
            if error_msg is not None:
                self._validation_error_messages[field_name] = error_msg

    def _handle_value_change(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        if len(self._validation_error_messages.get(field_name, '')) > 0:
            return

        fi = self._fields[field_name]
        # For modelselect: _from_widget_value_to_current_item sets the hidden FK field
        # (e.g. author_id) but intentionally does NOT set the relationship object on
        # _current_item (to avoid SQLAlchemy cascade-inserting the detached related
        # instance on session.add()). Compare and propagate the FK field instead.
        if fi.widget_type == 'modelselect':
            fk_field = f'{field_name}_id'
            if fk_field not in getattr(type(self._current_item), 'model_fields', {}):
                return
            old_value = getattr(self._validated_item, fk_field, None)
            new_value = getattr(self._current_item, fk_field, None)
            if old_value == new_value:
                return
            setattr(self._validated_item, fk_field, new_value)
        else:
            old_value = getattr(self._validated_item, field_name)
            new_value = getattr(self._current_item, field_name)
            if old_value == new_value:
                return
            setattr(self._validated_item, field_name, new_value)

        if self.autosave and self._item_adapter is not None:
            self.save()

        fce = FieldChangeEventArguments(
            sender=value_change_event.sender,
            client=value_change_event.client,
            form=self,
            field_name=field_name,
            previous_value=old_value,
            value=new_value,
        )
        for handler in self._change_handlers:
            handle_event(handler, fce)

    def _handle_validate_and_change(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        self._handle_validate(field_name, value_change_event)
        self._handle_value_change(field_name, value_change_event)
