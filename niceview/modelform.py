from dataclasses import dataclass
import inspect
import logging
from typing import Any, Self, TypeVar, Unpack
import typing
from pathlib import Path
import typing_extensions
from pydantic import BaseModel, TypeAdapter

from nicegui import ui
from nicegui.events import Handler, UiEventArguments, ValueChangeEventArguments, handle_event

from niceview.dataadapter import BoundItem, ConflictError, StorageError, JsonAdapter, CollectionAdapter, ItemAdapter
from niceview.fieldinfo import FieldInfo, _FieldInfoInputs, _merge_field_infos
from niceview.fields import Fields, LayoutField, LayoutGroup
from niceview.style import ChromeStyle, NotifyKind, chrome_notify, get_chrome_style, get_field_style
from niceview.text import ChromeText, get_chrome_text, text_of
from niceview.widgets import (
    DESCRIPTION_AS,
    DescriptionTarget,
    CONTROL_WIDGETS,
    INPUT_BASED_WIDGETS,
    TEXT_INPUT_WIDGETS,
    VALIDATED_WIDGETS,
    CheckboxGroup,
    apply_field_info,
    create_widget,
    field_value,
    required_error,
    run_validation,
    to_widget_value,
)

if typing.TYPE_CHECKING:
    # Only for the FormWidget type alias below; imported lazily elsewhere in this module
    # to avoid a circular import (editwrapper.py imports ModelForm from this module).
    from niceview.modelgrid import ModelGrid
    from niceview.editwrapper import EditGridWrapper

log = logging.getLogger('niceview')


@dataclass(kw_only=True, slots=True)
class FieldChangeEventArguments(UiEventArguments):
    form: 'ModelForm'
    field_name: str
    previous_value: Any
    value: Any


# Any type ModelForm.widgets[field_name] / w() may return: a native NiceGUI element for most
# fields, or one of the composite widgets (ModelGrid, EditGridWrapper, CheckboxGroup) for
# editgrid / checkbox_group fields — none of which are ui.element subclasses.
if typing.TYPE_CHECKING:
    FormWidget: typing.TypeAlias = ui.element | ModelGrid | EditGridWrapper | CheckboxGroup
else:
    FormWidget = object

W = TypeVar('W', bound=FormWidget)


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

    layout: list
    """Inline field layout: a nested list of field names. Same notation as a Meta.profiles
    entry — a nested list opens a row (rows and columns alternate), a leading '# Title' makes
    the group a card, '## Title' gives it the same heading without the card, a leading
    ':classes' replaces the container's classes, and a field name may carry its own classes
    after a colon ('street:sm:w-2/3')."""

    base_props: str
    """Quasar props applied to every field of this form (e.g. 'outlined dense'). Additive: the
    field's own props are merged on top, per key, so a field can add or change a single prop."""

    default_classes: str
    """CSS classes for every field of this form that brings none of its own (e.g. 'w-full').
    A fallback, not a base: any classes on the field or in the layout replace it wholesale."""

    autosave: bool
    """Whether to automatically save the form on field change. Defaults to False (OFF)."""

    local_tz: str | None
    """Local timezone name for datetime display (e.g. 'Europe/Berlin'). Defaults to None (system local timezone)."""

    on_change: Handler[FieldChangeEventArguments]
    """Callback to execute when value changes. To reduce the number of change events, fields like ui.input or ui.number also have to loose focus (blur)."""

    required_marker: str | None
    """Appended to the label of a required field. Defaults to ' *'; None renders no marker."""

    required_message: str
    """Validation message for an empty required field. Defaults to 'Required'."""

    description_as: 'DescriptionTarget'
    """Where a field's `description` (from pydantic's `description=`) is shown: 'tooltip'
    (default), 'hint' below the widget, or None to not show it at all. A field that sets `hint`
    or `tooltip` explicitly always wins over this."""

    chrome_style: 'ChromeStyle | None'
    """Look of the section titles of this form's layout. Replaces the application-wide default
    of niceview.style.set_chrome_style() wholesale — derive it with ChromeStyle.derived()."""

    chrome_text: 'ChromeText | None'
    """Texts of this form. Replaces the application-wide default of
    niceview.text.set_chrome_text() wholesale — derive it with ChromeText.derived()."""


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
    _warned_nonfield: bool
    widgets: dict[str, Any]

    autosave: bool
    local_tz: str | None
    required_marker: str | None
    required_message: str
    description_as: DescriptionTarget
    base_props: str | None
    default_classes: str | None
    _chrome_style: 'ChromeStyle | None'
    _chrome_text: 'ChromeText | None'

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
        layout = _get_param('layout', None)
        self._fields = Fields(item_type, include, exclude, field_infos, profile=profile, layout=layout)
        self._current_item = None
        self._validated_item = None
        self._validation_error_messages = {}
        self._nonfield_validation_errors = []
        self._nonfield_error_element = None
        self._warned_nonfield = False
        self.widgets = {}

        self._chrome_style = kwargs.pop('chrome_style', None)  # type: ignore[misc]
        self._chrome_text = kwargs.pop('chrome_text', None)  # type: ignore[misc]
        text = self._chrome_text or get_chrome_text()

        self.autosave = _get_param('autosave', False)
        self.local_tz = _get_param('local_tz', None)
        self.required_marker = _get_param('required_marker', text_of(text.required_marker))
        self.required_message = _get_param('required_message', text_of(text.required_message))
        self.description_as = _get_param('description_as', DESCRIPTION_AS)
        self.base_props = _get_param('base_props', None)
        self.default_classes = _get_param('default_classes', None)

        if on_change_callback := kwargs.pop('on_change', None):
            self.on_change(on_change_callback)

        if len(kwargs) > 0:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(kwargs.keys())}")

    @property
    def _style(self) -> ChromeStyle:
        return self._chrome_style or get_chrome_style()

    @property
    def _text(self) -> ChromeText:
        return self._chrome_text or get_chrome_text()

    def _notify(self, template: Any, kind: NotifyKind, **params: Any) -> None:
        """One of niceview's notifications: text from ChromeText, delivery from ChromeStyle."""
        chrome_notify(text_of(template, **params), kind, self._style)

    # --- factory methods ---------------------------------------------------

    @typing.overload
    @classmethod
    def from_item(cls, item: BaseModel, /, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self: ...
    @typing.overload
    @classmethod
    def from_item(cls, item_type: type[BaseModel], item: BaseModel, /, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self: ...
    @classmethod
    def from_item(cls, item_type_or_item: 'type[BaseModel] | BaseModel', item: 'BaseModel | None' = None, /, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
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
    def from_adapter(cls, item_type: type[BaseModel], adapter: 'CollectionAdapter | ItemAdapter', key: str | None = None, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm bound to an adapter.

        With key: wraps CollectionAdapter + key in a BoundItem.
        Without key: treats adapter directly as an ItemAdapter (e.g. JsonAdapter).
        """
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")
        instance = cls(item_type, **kwargs)
        if key is not None:
            instance.load(BoundItem(adapter, key))  # type: ignore[arg-type]
        else:
            instance.load(adapter)  # type: ignore[arg-type]
        return instance

    @classmethod
    def from_json(cls, item_type: type[BaseModel], json_path: Path, *, create_if_not_exist: bool = True, lock_field: str | None = None, created_field: str | None = None, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm bound to a single-item JSON file.
        The file is created with default values if it does not exist.
        Calls save() to persist changes; calls refresh() to re-read from disk.
        """
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")
        instance = cls(item_type, **kwargs)
        instance.load(JsonAdapter(item_type, json_path, create_if_not_exist=create_if_not_exist, lock_field=lock_field, created_field=created_field))
        return instance

    # --- item and form state management ------------------------------------

    @property
    def item(self) -> BaseModel:
        """
        The last state of the edited item that validated as a whole — the state save() would
        persist. While any validation error is present the item keeps its previous values; the
        values currently in the widgets are available as `draft`.

        The object identity is stable across edits (the form writes fields in place), so
        NiceGUI bindings such as bind_text_from(form.item, 'name') keep working.
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

    @property
    def draft(self) -> BaseModel:
        """
        The current widget values as a model instance — including values that fail validation
        and are therefore not in `item` yet. A copy: mutating it does not affect the form.
        """
        if self._current_item is None:
            raise ValueError("No item set. Use from_item(), from_json(), from_adapter(), or load() first.")
        return self._current_item.model_copy()

    def _set_item(self, value: BaseModel, in_place: bool = False) -> None:
        """
        Internal item assignment — bypasses the adapter-bound guard.

        in_place=True copies the values into the existing item instead of replacing it, so that
        NiceGUI bindings on form.item survive (used by refresh() and save(), which return the
        same logical item; load() navigates to a different one and rebinds).
        """
        if not (in_place and self._copy_into_item(value)):
            self._validated_item = value
        self._current_item = self._validated_item.model_copy()  # type: ignore[union-attr]
        self._push_item_to_widgets()
        self._validate()

    def _copy_into_item(self, source: BaseModel) -> bool:
        """
        Copy source's field values into the existing item, keeping its identity.
        Returns False when that is not possible (no item yet, different type, frozen model) —
        the caller then falls back to replacing the item.
        """
        target = self._validated_item
        if target is None or type(target) is not type(source):
            return False
        if type(target).model_config.get('frozen'):
            return False
        for name, field in type(target).model_fields.items():
            if field.frozen:
                continue  # pydantic raises on assignment to a frozen field
            setattr(target, name, getattr(source, name))
        return True

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
        # The overloads guarantee: with key -> CollectionAdapter, without key -> ItemAdapter.
        item_adapter: ItemAdapter
        if key is not None:
            item_adapter = BoundItem(typing.cast(CollectionAdapter, adapter), key)
        else:
            item_adapter = typing.cast(ItemAdapter, adapter)
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

    def refresh(self, notify: bool = True) -> None:
        """Reload the item from the adapter, discarding any unsaved edits.

        notify=False suppresses the ui.notify popup (e.g. for programmatic refreshes)."""
        if not self.adapter_bound:
            raise ValueError("No adapter set. Use from_adapter(), from_json(), or load() first.")
        item = self._item_adapter.read()  # type: ignore[union-attr]
        if not isinstance(item, BaseModel):
            raise TypeError(f"item must be a BaseModel instance, got {type(item)}")
        self._set_item(item, in_place=True)  # same item reloaded: keep bindings alive
        if notify:
            self._notify(self._text.form_refreshed, 'positive')

    def save(self, notify: bool = True) -> None:
        """Persist the current item to the adapter. No-op if validation errors are present.

        notify=False suppresses all ui.notify popups (success and error); errors are
        still logged and reflected in the form's validation state."""
        if self._item_adapter is None:
            raise ValueError("No adapter set. Use from_adapter(), from_json(), or load() first.")

        if self.has_validation_errors:
            if notify:
                self._notify(self._text.validation_errors, 'negative')
            return

        try:
            updated = self._item_adapter.save(self.item)
        except (ConflictError, StorageError) as e:
            log.error(f"save failed: {e}")
            if notify:
                self._notify(str(e), 'negative')  # the adapter's own message, not one of ours
            return
        if updated is not None and updated is not self._validated_item:
            # Adapters may return a new instance (e.g. with generated ids). Copy the values in
            # instead of rebinding, so bindings on form.item survive a save.
            if not self._copy_into_item(updated):
                self._validated_item = updated
            self._current_item = self._validated_item.model_copy()  # type: ignore[union-attr]
        if notify:
            self._notify(self._text.form_saved, 'positive')

    # --- widget management -------------------------------------------------

    @typing.overload
    def w(self, field_name: str) -> FormWidget: ...
    @typing.overload
    def w(self, field_name: str, widget_type: type[W]) -> W: ...
    def w(self, field_name: str, widget_type: 'type[W] | None' = None) -> 'FormWidget | W':
        """
        Return the rendered widget for a field, with optional type narrowing.

          form.w('name')                   # → ui.element (or ModelGrid / EditGridWrapper /
                                            #   CheckboxGroup for editgrid / checkbox_group fields)
          form.w('name', ui.input)         # → ui.input        (typed; raises TypeError if mismatch)
          form.w('perms', CheckboxGroup)   # → CheckboxGroup

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
            raise TypeError(f"repositories must be a dictionary, got {type(repositories)}")
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

    def _wire_text_input(self, widget: Any, field_name: str) -> None:
        """Wire a text-input widget: validate on change, commit on blur."""
        widget.on_value_change(lambda vce, fn=field_name: self._handle_validate(fn, vce))
        widget.on('blur', lambda e, fn=field_name: self._handle_blur_event(fn, e))

    def _wire_immediate(self, widget: Any, field_name: str) -> None:
        """Wire an immediate widget: validate and commit on value change."""
        widget.on_value_change(lambda vce, fn=field_name: self._handle_validate_and_change(fn, vce))

    def _wire_widget(self, field_name: str, widget_type: str, widget: Any) -> None:
        """
        Connect a widget created by niceview.widgets to the form: change events, and the
        validation callback for the widget types that can show a message.
        Wiring happens after the initial value has been set, so that pushing the item's
        value into the widget does not fire a change event.
        """
        if widget_type in TEXT_INPUT_WIDGETS:
            self._wire_text_input(widget, field_name)
        else:
            self._wire_immediate(widget, field_name)
        if widget_type in VALIDATED_WIDGETS:
            widget.validation = lambda value, fn=field_name: self._get_field_error(fn, value)
            # return_result=False: NiceGUI refuses to return a result for an async validation
            # function, and field_info.validation may well be one.
            widget.validate(return_result=False)

    # --- widget rendering methods ------------------------------------------

    def _prepare_modelselect(self, field_name: str, field_info: FieldInfo) -> 'ui.select | None':
        """
        Resolve the repository of a modelselect field into field_info.options, so that the
        field can be rendered as a plain select.
        Returns None on success, or a disabled placeholder widget if no repository is
        registered for the field's item type.
        """
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
            return widget

        repo = self._model_repositories[field_info.item_type]
        field_info.options = {repo.key_from_item(item): str(item) for item in repo}
        return None

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
        from niceview.editwrapper import EditGridWrapper
        from niceview.modelgrid import ModelGrid, TableItemEventArguments
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

                def matches_parent(item: Any, fk: str = fk_field, val: Any = parent_value) -> bool:
                    return getattr(item, fk, None) == val

                data = FilteredAdapter(repo, predicate=matches_parent, defaults={fk_field: parent_value})
            else:
                data = ListAdapter(field_info.item_type, getattr(self._validated_item, field_name))
        else:
            data = ListAdapter(field_info.item_type, getattr(self._validated_item, field_name))

        widget = ModelGrid(field_info.item_type, data)
        # An embedded grid is a section of the form, not a page of its own: its title takes the
        # chrome's section size, one step below the title of the wrapper around the form.
        chrome = self._style
        section_style = chrome.replace(title_classes=f'{chrome.section_title_classes} grow')
        if field_info.editable:
            edit_widget = EditGridWrapper(widget, title=field_info.label, chrome_style=section_style,
                                          chrome_text=self._chrome_text, place='form')
            if self._model_repositories:
                edit_widget.with_repositories(self._model_repositories)
            edit_widget.on_change(notify_change)
            edit_widget.render()
            return edit_widget  # type: ignore[return-value]
        else:
            ui.label(field_info.label).classes(chrome.section_title_classes)
            widget.render()
            return widget  # type: ignore[return-value]

    def _render_widget(self, field_name: str, field_info: FieldInfo) -> Any:
        """
        Create and wire a widget for the given field, based on its widget_type.

        The widget itself is built by niceview.widgets — the same code path as the
        model-free render_field(); this method adds what needs the model: the item's
        value, change events, validation state and the model-backed widget types.
        """
        if not field_info:
            raise ValueError(f"Field info for {field_name} not found")
        widget_type = field_info.widget_type
        if not widget_type:
            raise ValueError(f"Widget type for field {field_name} not found in field info")

        # editgrid brings its own chrome, styling and change handling.
        if widget_type == 'editgrid':
            return self._render_editgrid_widget(field_name, field_info)

        # modelselect is a select over a repository: resolve the options first, then let it
        # fall through to the normal select rendering below.
        if widget_type == 'modelselect':
            placeholder = self._prepare_modelselect(field_name, field_info)
            if placeholder is not None:
                apply_field_info(placeholder, field_info, self.description_as)
                return placeholder

        def push_value(widget: Any) -> None:
            self._from_current_item_to_widget_value(field_name, widget_type, widget)

        widget = create_widget(field_info, field_name, push_value, self.required_marker, self.description_as)
        self._wire_widget(field_name, widget_type, widget)
        return widget

    def render_field(self, field_name: str, **kwargs: Unpack[_FieldInfoInputs]) -> Any:
        """
        Render a single named field in the current NiceGUI context.

        Returns the created widget so callers can style it immediately:
          form.render_field('name').classes('w-full')

        Optional kwargs override FieldInfo attributes for this render only:
          form.render_field('name', label='Short name')
          form.render_field('is_active', label='')   # suppress label

        Unlike render(), this does not reset existing widgets — call it multiple
        times inside any layout structure to position fields individually.
        The non-field error label is not rendered; call render_nonfield_errors()
        separately to place it wherever needed.

        Raises ValueError for unknown or hidden fields.
        """
        if field_name not in self._fields:
            raise ValueError(f"Field '{field_name}' is not in the form's field set")
        field_info = self._fields[field_name]
        if not field_info:
            raise ValueError(f"Field info for '{field_name}' not found")
        if field_info.hidden:
            raise ValueError(f"Field '{field_name}' is hidden and cannot be rendered individually")
        if kwargs:
            field_info = _merge_field_infos(field_info, FieldInfo(**kwargs))
        widget = self._render_widget(field_name, self._styled(field_info))
        self.widgets[field_name] = widget
        return widget

    def _styled(self, field_info: FieldInfo, layout_classes: str | None = None, in_row: bool = False) -> FieldInfo:
        """
        Apply the styling cascade to a field. Props and classes are handled differently, and
        the difference is not arbitrary: a Quasar prop has a key, so props from two sources
        merge per key and the later one wins. A CSS class has no key — 'w-full w-1/2' is
        decided by stylesheet order, not by the order in the class list — so classes cannot be
        merged meaningfully and the most specific source replaces the others wholesale.

          props:   the category's props (FieldStyle) + base_props + the field's own props
                   (additive, per key, the narrower source wins)
          classes: layout classes, else the field's own classes, else the form's
                   default_classes, else the application's

        In a row, 'min-w-0' is always added — it is layout mechanics, not styling, and cannot
        conflict with a width utility. 'flex-1' (equal share) is added only when no source
        asked for a width of its own, because it sets flex-basis to 0 and would silently
        override one.
        """
        field_style = get_field_style()
        widget_type = field_info.widget_type or ''
        if widget_type in INPUT_BASED_WIDGETS:
            category_props = field_style.input_props
        elif widget_type in CONTROL_WIDGETS:
            category_props = field_style.control_props
        else:
            category_props = ''  # 'editgrid' brings its own chrome, it is not a field with props

        explicit_classes = layout_classes or field_info.classes
        classes = [explicit_classes or self.default_classes or field_style.default_classes]
        if in_row:
            classes.append('min-w-0' if explicit_classes else 'flex-1 min-w-0')
        props = [category_props, self.base_props, field_info.props]

        overrides: dict[str, Any] = {}
        if any(classes):
            overrides['classes'] = ' '.join(c for c in classes if c)
        if any(props):
            overrides['props'] = ' '.join(p for p in props if p)
        if not overrides:
            return field_info
        return _merge_field_infos(field_info, FieldInfo(**overrides))

    def render_nonfield_errors(self) -> ui.label:
        """
        Render the non-field (model-level) validation error label in the current NiceGUI context.

        Returns the created ui.label so callers can style it:
          form.render_nonfield_errors().classes('q-mt-sm')

        Call this separately when using render_field() to control its placement.
        render() calls this automatically at the end.
        """
        self._nonfield_error_element = ui.label('').classes('text-negative w-full')
        self._nonfield_error_element.set_visibility(False)
        return self._nonfield_error_element

    def render(self) -> Self:
        """
        Render all non-hidden fields followed by the non-field error label.

        Fields are arranged according to the form's layout (from `layout=`, from the selected
        `Meta.profiles` entry, or simply one below the other). Use render_field() and
        render_nonfield_errors() instead when a layout the notation cannot express is needed.
        """
        self.widgets = {}
        self._render_group(self._fields.layout)
        self.render_nonfield_errors()
        return self

    def _render_group(self, group: LayoutGroup) -> None:
        """Render a layout group's children into the current NiceGUI context."""
        for child in group.children:
            if isinstance(child, LayoutField):
                field_info = self._fields[child.name]
                if not field_info:
                    raise ValueError(f"Field {child.name} not found in field_infos")
                if field_info.hidden:
                    continue
                self.widgets[child.name] = self._render_widget(
                    child.name, self._styled(field_info, child.classes, in_row=group.row)
                )
            else:
                with self._layout_container(child):
                    self._render_group(child)

    def _layout_container(self, group: LayoutGroup) -> ui.element:
        """
        The container for a nested layout group: a section for a titled group ('#' draws a card
        around it, '##' only the heading), otherwise a row or a column. `:classes` replaces the
        defaults rather than adding to them — Tailwind resolves a duplicate utility by
        stylesheet order, not by the order in the class list.
        """
        if group.title is not None:
            chrome = self._style
            section = (ui.card().props('flat bordered').classes(group.classes or 'w-full')
                       if group.card else ui.column().classes(group.classes or 'w-full gap-4'))
            with section:
                ui.label(group.title).classes(chrome.card_title_classes if group.card
                                              else chrome.section_title_classes)
            return section
        if group.row:
            return ui.row().classes(group.classes or 'w-full items-start gap-4')
        return ui.column().classes(group.classes or 'w-full gap-4')

    # --- value conversion --------------------------------------------------

    def _from_current_item_to_widget_value(self, field_name: str, widget_type: str, widget: Any) -> None:
        """Push the current item's field value into the widget."""
        value = getattr(self._current_item, field_name)

        if widget_type == 'modelselect':
            # The widget holds the repository key of the related item, not the item itself.
            item_type = self._fields[field_name].item_type
            assert item_type is not None, f"item_type for field '{field_name}' must not be None"
            repository = self._model_repositories[item_type]
            if not repository:
                raise ValueError(f"Model repository for {item_type.__name__} not found in form's model repositories")
            widget.value = repository.key_from_item(value) if value is not None else None
            return

        widget.value = to_widget_value(self._fields[field_name], value, local_tz=self.local_tz)  # type: ignore[attr-defined]

    def _from_widget_value_to_current_item(self, field_name: str) -> None:
        """
        Read the widget value, convert it to the model type, and write it into _current_item.
        Exceptions should be handled by the caller.
        """
        if field_name not in self.widgets:
            raise ValueError(f"Widget for field {field_name} not found")
        widget = self.widgets[field_name]
        field_info = self._fields[field_name]

        if field_info.widget_type == 'modelselect':
            item_type = field_info.item_type
            assert item_type is not None, f"item_type for field '{field_name}' must not be None"
            repository = self._model_repositories[item_type]
            if not repository:
                raise ValueError(f"Model repository for {item_type.__name__} not found in form's model repositories")
            key = widget.value  # type: ignore[attr-defined]
            value = repository.read(key) if key is not None else None
            # Sync FK field (e.g. author -> author_id) so pydantic validation sees the selection.
            # Do NOT also set the relationship attribute: SQLAlchemy would cascade-insert the
            # detached related instance, violating UNIQUE constraints on the related table.
            fk_field = f'{field_name}_id'
            assert self._current_item is not None
            if fk_field in type(self._current_item).model_fields:
                fk_val: Any
                if value is not None:
                    key_str = repository.key_from_item(value)
                    fk_type = type(self._current_item).model_fields[fk_field].annotation
                    fk_val = TypeAdapter(fk_type).validate_python(key_str)
                else:
                    fk_val = None
                setattr(self._current_item, fk_field, fk_val)
                return  # FK synced; skip setting the relationship object
        else:
            try:
                value = field_value(widget, field_info, local_tz=self.local_tz)
            except ValueError as e:
                raise ValueError(f"Field '{field_name}': {e}") from e

        setattr(self._current_item, field_name, value)

    # --- validation and event handling ------------------------------------

    def _own_field_error(self, field_name: str, value: Any) -> str | None:
        """
        Validation layer 1 for a field: `required` first, then field_info.validation — the
        rules that need no model and behave exactly as they do in render_field().
        An async validation function is displayed by the widget itself but skipped here: a
        commit cannot wait for it. See docs/components.md.
        """
        field_info = self._fields[field_name]
        error = required_error(field_info, value, self.required_message)
        if error is not None:
            return error
        result = run_validation(field_info.validation, value)
        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()  # not awaited here — avoid "coroutine was never awaited"
            return None
        return result

    def _get_field_error(self, field_name: str, value: Any) -> Any:
        """
        NiceGUI validation callback, in layer order: the field's own rules (required, then
        field_info.validation) first, the model's error for this field second.
        Returns an awaitable when field_info.validation is an async function; NiceGUI resolves
        it in the background.
        """
        field_info = self._fields[field_name]
        error = required_error(field_info, value, self.required_message)
        if error is not None:
            return error
        result = run_validation(field_info.validation, value)
        if inspect.isawaitable(result):
            async def _combined() -> str | None:
                return await result or self._validation_error_messages.get(field_name)
            return _combined()
        return result or self._validation_error_messages.get(field_name)

    def _validate(self, extra_errors: 'dict[str, str] | None' = None) -> None:
        """
        Run all validation layers and refresh the error display.
        Layer 1 (required / field_info.validation) is evaluated per rendered widget and takes
        precedence over the model's message for the same field; `extra_errors` (conversion
        failures) wins over both.
        """
        if self._current_item is None:
            return
        field_errors, nonfield_errors = self._fields.validation_errors(self._current_item.model_dump())

        for field_name, widget in self.widgets.items():
            if not hasattr(widget, 'value'):
                continue  # composite widgets (editgrid) are not validated per value
            own_error = self._own_field_error(field_name, widget.value)
            if own_error:
                field_errors[field_name] = own_error
        if extra_errors:
            field_errors.update(extra_errors)

        self._validation_error_messages = field_errors
        self._nonfield_validation_errors = nonfield_errors

        if self._nonfield_error_element is not None:
            if nonfield_errors:
                self._nonfield_error_element.set_text(' | '.join(nonfield_errors))
                self._nonfield_error_element.set_visibility(True)
            else:
                self._nonfield_error_element.set_visibility(False)
        elif nonfield_errors and self.widgets and not self._warned_nonfield:
            self._warned_nonfield = True
            log.warning(
                "Model-level validation errors are blocking the form but are not displayed: "
                "call render_nonfield_errors() to place the message. Errors: "
                + ' | '.join(nonfield_errors)
            )

        for widget in self.widgets.values():
            if hasattr(widget, 'validate') and callable(widget.validate):
                # return_result=False: NiceGUI refuses to return a result for async validations
                widget.validate(return_result=False)

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
        """Layers 1 and 2: validate the raw widget value, then convert it into the draft."""
        raw_value = value_change_event.sender.value  # type: ignore[attr-defined]
        extra_errors: dict[str, str] = {}

        if self._own_field_error(field_name, raw_value) is None:
            # Only a value the field itself accepts is converted and written to the draft, so
            # the model never sees a value the user was already told is wrong.
            if getattr(self._current_item, field_name, None) != raw_value:
                try:
                    self._from_widget_value_to_current_item(field_name)
                except Exception:
                    extra_errors[field_name] = "Error interpreting widget value"

        self._validate(extra_errors)

    def _committed_attr(self, field_name: str) -> str:
        """
        The attribute that carries a field's value on the item.
        For modelselect this is the FK field (e.g. author -> author_id): the draft holds the FK,
        not the relationship object, so that SQLAlchemy does not cascade-insert a detached
        instance on session.add().
        """
        if self._fields[field_name].widget_type == 'modelselect':
            fk_field = f'{field_name}_id'
            if fk_field in getattr(type(self._current_item), 'model_fields', {}):
                return fk_field
        return field_name

    def _handle_value_change(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        """
        Layer 3: write the draft into the item — but only when the item validates as a whole.

        All changed fields are committed together, not just the one that fired the event: an
        edit made while a cross-field error stood must not be lost when that error clears.
        The item is written in place, so NiceGUI bindings on form.item keep working.
        """
        if self._current_item is None or self._validated_item is None:
            return
        if self.has_validation_errors:
            return

        changes: list[tuple[str, str, Any, Any]] = []
        for name in self._fields:
            if self._fields[name].widget_type == 'editgrid':
                continue  # the grid mutates the item's list in place; nothing to sync
            attr = self._committed_attr(name)
            old_value = getattr(self._validated_item, attr, None)
            new_value = getattr(self._current_item, attr, None)
            if old_value != new_value:
                changes.append((name, attr, old_value, new_value))
        if not changes:
            return

        for _, attr, _, new_value in changes:
            setattr(self._validated_item, attr, new_value)

        if self.autosave and self._item_adapter is not None:
            self.save()

        for name, _, old_value, new_value in changes:
            fce = FieldChangeEventArguments(
                sender=value_change_event.sender,
                client=value_change_event.client,
                form=self,
                field_name=name,
                previous_value=old_value,
                value=new_value,
            )
            for handler in self._change_handlers:
                handle_event(handler, fce)

    def _handle_validate_and_change(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        self._handle_validate(field_name, value_change_event)
        self._handle_value_change(field_name, value_change_event)
