from dataclasses import dataclass
import datetime
from enum import StrEnum
from typing import Any, List, Literal, Self, Unpack
import typing
from pathlib import Path
from zoneinfo import ZoneInfo
from sqlalchemy import Enum
import typing_extensions
from pydantic import BaseModel, TypeAdapter, ValidationError

from nicegui import ui
from nicegui.events import Handler, UiEventArguments, ValueChangeEventArguments, handle_event
from nicegui.dataclasses import KWONLY_SLOTS

from niceview.dataadapter import JsonModelAdapter, ModelDataAdapter, SingleItemAdapter, SqlModelAdapter
from niceview.fieldinfo import FieldInfo
from niceview.fields import Fields


@dataclass(**KWONLY_SLOTS)
class FieldChangeEventArguments(UiEventArguments):
    form: 'ModelForm'
    field_name: str
    old_value: Any
    new_value: Any


class _ModelFormOptionInputs(typing_extensions.TypedDict, total=False):
    """
    Kwarg Options for the UiForm class.
    """
    include: list[str] | str
    exclude: list[str] | str
    field_info: dict[str, FieldInfo]

    title: str
    description: str
    classes: str
    tailwind: str
    style: str
    props: str

    autosave: bool
    """Whether to automatically save the form on field change. Defaults to False (OFF)."""

    refresh_button: str | None
    """Text for the refresh button. Empty string shows icon only. Requires item_model. If not provided, no refresh button will be shown (default)."""

    save_button: str | None
    """Text for the save button. Empty string shows icon only. Requires item_model. If not provided, no save button will be shown (default)."""

    local_tz: str | None
    """Local timezone name for datetime display (e.g. 'Europe/Berlin'). Defaults to None (system local timezone)."""

    on_change: Handler[FieldChangeEventArguments]
    """Callback to execute when value changes. To reduce the number of change events, fields like ui.input or ui.number also have to loose focus (blur)."""


class ModelForm():
    """
    A form class that can be used to create forms for Pydantic models.
    Configuration options can be defined in the item's Meta class, 
    or as keyword arguments when creating the form.
    """
    _item_type: type[BaseModel]
    _item_model: SingleItemAdapter | None
    _item_key: str | int | None
    _model_repositories: dict[str, ModelDataAdapter]
    _change_handler: Handler[FieldChangeEventArguments]

    _fields: Fields
    _current_item: BaseModel | None
    _validated_item: BaseModel | None
    _validation_error_messages: dict[str, str]
    _nonfield_validation_errors: list[str]
    _nonfield_error_element: Any
    widgets: dict[str, ui.element]

    title: str
    description: str
    classes: str
    tailwind: str
    style: str
    props: str

    autosave: bool
    local_tz: str | None
    refresh_button: str | None
    save_button: str | None

    def __init__(self, item_type: type[BaseModel], **kwargs: Unpack[_ModelFormOptionInputs]) -> None:
        """
        Initialize the form with a model and optional keyword arguments.
        The model must be a subclass of BaseModel.
        The keyword arguments can be used to set the fields, field_infos, and other options.

        Binding:
        - The form keeps a reference to the model and the current model.
        - The reference to the model is updated when the form is successfully validated. 
          Therefore it is called the validated model.
        - The current model is the one that is currently being edited.
        - The current model is validated after each change.
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
        self._item_model = None
        self._item_key = None
        self._model_repositories = {}
        self._change_handlers: list[Handler[FieldChangeEventArguments]] = []

        include = _get_param('include', '__all__')
        exclude = _get_param('exclude', '')
        field_info = _get_param('field_info', {})
        self._fields = Fields(item_type, include, exclude, field_info)
        self._current_item = None
        self._validated_item = None
        self._validation_error_messages = {}
        self._nonfield_validation_errors = []
        self._nonfield_error_element = None
        self.widgets = {}

        self.title = _get_param('title', '')
        self.description = _get_param('description', '')
        self.classes = _get_param('classes', '')
        self.tailwind = _get_param('tailwind', '')
        self.style = _get_param('style', '')
        self.props = _get_param('props', '')

        self.autosave = _get_param('autosave', False)
        self.local_tz = _get_param('local_tz', None)
        self.refresh_button = _get_param('refresh_button', None)
        self.save_button = _get_param('save_button', None)

        if on_change_callback := kwargs.pop('on_change', None):
            self.on_change(on_change_callback)

        if len(kwargs) > 0:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(kwargs.keys())}")


    @classmethod
    def from_item(cls, item_type_or_item: 'type[BaseModel] | BaseModel', item: 'BaseModel | None' = None, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm from a model instance.

        Two call forms for API symmetry with from_adapter() and from_json():
          from_item(instance)         — convenience; item_type inferred from instance
          from_item(Type, instance)   — explicit type
        """
        if item is None:
            if not isinstance(item_type_or_item, BaseModel):
                raise TypeError(f"item must be a BaseModel instance, got {type(item_type_or_item)}")
            item = item_type_or_item
            item_type = type(item)
        else:
            item_type = item_type_or_item  # type: ignore[assignment]
            if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
                raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")
            if not isinstance(item, BaseModel):
                raise TypeError(f"item must be a BaseModel instance, got {type(item)}")
        ret = cls(item_type, **kwargs)
        ret.item = item
        return ret
    
    @classmethod
    def from_adapter(cls, item_type: type[BaseModel], adapter: SingleItemAdapter, key: str | int, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm bound to any ModelDataAdapter.
        """
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")
        instance = cls(item_type, **kwargs)
        instance.load(adapter, key)
        return instance

    @classmethod
    def from_json(cls, item_type: type[BaseModel], json_path: Path, create_if_not_exist: bool = True, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm bound to a JSON file via JsonModelAdapter.
        """
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")
        adapter = JsonModelAdapter(item_type, json_path, create_if_not_exist=create_if_not_exist)
        instance = cls(item_type, **kwargs)
        instance.load(adapter, JsonModelAdapter.DEFAULT_KEY)
        return instance

    @property
    def item(self) -> BaseModel:
        """
        Get the current (validated) item of the form.
        This is the item that is currently being edited.
        """
        if not self._validated_item:
            raise ValueError("No item set. Use from_item(), from_json(), from_adapter(), or load() first.")
        return self._validated_item

    @item.setter
    def item(self, value: BaseModel) -> None:
        """
        Set the form's (validated) item for editing.
        Editing the form will modify this item directly.
        """
        if not isinstance(value, BaseModel):
            raise TypeError(f"item must be a BaseModel instance, got {type(value)}")
        self._validated_item = value  # the validated item is modified in-place, so it is not a copy
        self._current_item = self._validated_item.model_copy()
        self._validate()
        self._push_item_to_widgets()


    def load(self, adapter: SingleItemAdapter, key: str | int) -> Self:
        """
        Load an item from a data adapter and make it the active item in the form.
        Use this for master-detail navigation (switching the displayed item at runtime).
        """
        self._item_model = adapter
        self._item_key = key
        item = self._item_model.read(key)
        if not isinstance(item, BaseModel):
            raise TypeError(f"item must be a BaseModel instance, got {type(item)}")
        self.item = item
        return self
    
    def set_model_repositories(self, repositories: dict[str, ModelDataAdapter]) -> Self:
        """
        Set the model repositories for the modelselect widgets in the form.
        This is a dictionary of model data adapters that can be used to read and write items.
        """
        if not isinstance(repositories, dict):
            raise TypeError(f"model_repositories must be a dictionary, got {type(dict)}")
        self._model_repositories = repositories
        return self

    def _push_item_to_widgets(self) -> None:
        """Push current item values into all rendered widgets."""
        for field_name, widget in self.widgets.items():
            widget_type = self._fields[field_name].widget_type
            if widget_type and widget_type != 'editgrid':
                self._from_current_item_to_widget_value(field_name, widget_type, widget)

    def _refresh(self) -> None:
        """
        Refresh the form by reloading the item from the model and pushing
        the new values into all rendered widgets.
        """
        if self._item_model is None or self._item_key is None:
            raise ValueError("No adapter set. Use from_adapter(), from_json(), or load() first.")
        self.load(self._item_model, self._item_key)
        ui.notify('Form refreshed', color='positive')

    def _save(self) -> None:
        """
        Save the current item to the model.
        """
        if self._item_model is None or self._item_key is None:
            raise ValueError("No adapter set. Use from_adapter(), from_json(), or load() first.")

        if self.has_validation_errors():
            ui.notify('Cannot save form: validation errors present', color='negative')
            return

        updated = self._item_model.update(self.item, str(self._item_key))
        if updated is not None and updated is not self._validated_item:
            self._validated_item = updated
            self._current_item = updated.model_copy()
        ui.notify('Form saved', color='positive')


    def on_change(self, callback: Handler[FieldChangeEventArguments]) -> Self:
        """
        Add a callback to be invoked when the form values change and 
        the new values are successfully validated.
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")
        self._change_handlers.append(callback)
        return self


    def _render_select_widget(self, field_name: str, field_info: FieldInfo, kwargs) -> ui.select:
        """
        Render a select widget for the given field name and field info.
        The select options are determined by the field info.
        """
        if not field_info.select_options:
            raise ValueError(f"Field {field_name} has no select options defined in FieldInfo")
        if callable(field_info.select_options):
            kwargs['options'] = (field_info.select_options)()
        else:
            kwargs['options'] = field_info.select_options

        widget = ui.select(**kwargs)

        self._from_current_item_to_widget_value(field_name, 'ui.select', widget)
        widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate_and_change(field_name, vce))
        widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)
        return widget


    def _render_modelselect_widget(self, field_name: str, field_info: FieldInfo, kwargs) -> ui.select:
        """
        Render a model select widget for the given field name and field info.
        The select options are determined by the field info.
        """
        if not field_info.item_type:
            raise ValueError(f"Field {field_name} is a model select but no item type is specified in FieldInfo or as a pydantic model type")

        if field_info.item_type.__name__ not in self._model_repositories:
            raise ValueError(f"Model repository for {field_info.item_type} not found in form's model repositories")

        field_info.select_options = dict(self._model_repositories[field_info.item_type.__name__].query_all_strs())
        widget = self._render_select_widget(field_name, field_info, kwargs)
        return widget


    def _render_editgrid_widget(self, field_name: str, field_info: FieldInfo) -> Any:
        from niceview.modeledit import EditGridWrapper
        from niceview.modelgrid import ModelGrid, TableItemEventArguments
        from niceview.dataadapter import ListModelAdapter

        def notify_change(e: TableItemEventArguments) -> None:
            if self.autosave:
                self._save()
            fce = FieldChangeEventArguments(
                sender=e.sender,
                client=e.client,
                form=self,
                field_name=field_name,
                old_value=None,
                new_value=e.item,
            )
            for handler in self._change_handlers:
                handle_event(handler, fce)

        if not field_info.item_type:
            raise ValueError(f"Field {field_name} is a list but no item type is specified in FieldInfo or as a pydantic model type")

        # work directly on the validated item instead of the current item because there is no need for validation
        data = ListModelAdapter(field_info.item_type, getattr(self._validated_item, field_name))
        widget = ModelGrid(
            field_info.item_type, data,
            classes=self.classes, tailwind=self.tailwind, style=self.style, props=self.props,
        )
        if field_info.editable:  # create an editable grid for the field
            edit_widget = EditGridWrapper(widget, title=field_info.label)
            edit_widget.on_change(notify_change)
            edit_widget.render()
            return edit_widget  # type: ignore[return-value]
        else:  # create a read-only grid for the field
            ui.label(field_info.label).classes('text-h6')
            widget.render()
            return widget  # type: ignore[return-value]


    def _render_widget(self, field_name: str, field_info: FieldInfo) -> ui.element:
        """
        Create a widget for the given field name and field info.
        The widget type is determined by the field info.
        """

        def get_kwargs_from_field_info(filter_list: list[str]) -> dict:
            """
            Get the keyword arguments from the field info for the given fields.
            """
            return {k: v for k in filter_list if (v := getattr(field_info, k)) is not None}

        if not field_info:
            raise ValueError(f"Field info for {field_name} not found")
        widget_type = field_info.widget_type
        if not widget_type:
            raise ValueError(f"Widget type for field {field_name} not found in field info")
        is_simple_widget = True  # whether the widget is a simple widget (e.g. input, number, textarea, checkbox, switch, select)
        widget: Any = None

        if widget_type == 'ui.input':
            widget = ui.input(**get_kwargs_from_field_info(['label', 'placeholder', 'password', 'password_toggle_button', 'autocomplete']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)

        elif widget_type == 'ui.number':
            widget = ui.number(**get_kwargs_from_field_info(['label', 'placeholder', 'min', 'max', 'precision', 'step', 'prefix', 'suffix', 'format']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)

        elif widget_type == 'ui.textarea':
            widget = ui.textarea(**get_kwargs_from_field_info(['label', 'placeholder']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)

        elif widget_type == 'ui.checkbox':
            widget = ui.checkbox(text=field_info.label)
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate_and_change(field_name, vce))
            # for checkboxes, we consider the validation errors irrelevant

        elif widget_type == 'ui.switch':
            widget = ui.switch(text=field_info.label)
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate_and_change(field_name, vce))
            # for switches, we consider the validation errors irrelevant

        elif widget_type == 'ui.select':
            widget = self._render_select_widget(field_name, field_info, get_kwargs_from_field_info(['label', 'with_input', 'multiple', 'clearable']))

        elif widget_type == 'ui.input_chips':
            widget = ui.input_chips(**get_kwargs_from_field_info(['label', 'new_value_mode']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)

        elif widget_type == 'datetime':
            widget = ui.input(**get_kwargs_from_field_info(['label', 'placeholder'])).props('type=datetime-local').props('step=1')
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)

        elif widget_type == 'date':
            widget = ui.input(**get_kwargs_from_field_info(['label', 'placeholder'])).props('type=date')
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)

        elif widget_type == 'time':
            widget = ui.input(**get_kwargs_from_field_info(['label', 'placeholder'])).props('type=time').props('step=1')
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)
        
        elif widget_type == 'timedelta':
            widget = ui.input(**get_kwargs_from_field_info(['label', 'placeholder']))
            self._from_current_item_to_widget_value(field_name, widget_type, widget)
            widget.on_value_change(lambda vce, field_name=field_name: self._handle_validate(field_name, vce))
            widget.on('blur', lambda e, field_name=field_name: self._handle_blur_event(field_name, e))
            widget.validation = lambda value, field_name=field_name: self._validation_errors(field_name, value)

        elif widget_type == 'editgrid':
            widget = self._render_editgrid_widget(field_name, field_info)
            is_simple_widget = False

        elif widget_type == 'modelselect':
            widget = self._render_modelselect_widget(field_name, field_info, get_kwargs_from_field_info(['label', 'with_input', 'multiple', 'clearable']))

        if not widget:
            raise ValueError(f"Invalid widget class: {widget_type}")

        if is_simple_widget:
            if not field_info.editable and hasattr(widget, 'disable') and callable(widget.disable):
                widget.disable()
            if field_info.tooltip and hasattr(widget, 'tooltip') and callable(widget.tooltip):
                widget.tooltip(field_info.tooltip)

            widget.classes(self.classes)
            if self.tailwind:
                widget.classes(self.tailwind)
            widget.style(self.style)
            widget.props(self.props)

        return widget


    def render(self) -> Self:
        """
        Render the form
        """
        if self.title or self.refresh_button is not None or self.save_button is not None:
            with ui.row().classes('w-full'):
                if self.title:
                    ui.label(self.title).classes('text-h6 font-bold')
                has_adapter = self._item_model is not None
                if (self.refresh_button is not None and has_adapter) or (self.save_button is not None and has_adapter):
                    ui.space()
                    with ui.button_group():
                        if self.refresh_button is not None and has_adapter:
                            ui.button(self.refresh_button, icon='refresh').tooltip('Refresh').props('dense flat').on_click(self._refresh)
                        if self.save_button is not None and has_adapter:
                            ui.button(self.save_button, icon='save').tooltip('Save').props('dense flat').on_click(self._save)

        if self.description:
            ui.markdown(self.description)

        self.widgets = {}
        for field_name in self._fields:
            field_info = self._fields[field_name]
            if not field_info:
                raise ValueError(f"Field {field_name} not found in ni_field_infos")
            if field_info.hidden:
                # Skip hidden fields
                continue
            # Render an editable field based on its widget class
            self.widgets[field_name] = self._render_widget(field_name, field_info)

        self._nonfield_error_element = ui.label('').classes('text-negative w-full')
        self._nonfield_error_element.set_visibility(False)

        return self


    def _from_current_item_to_widget_value(self, field_name: str, widget_type: str, widget) -> Self:
        """
        Set the value of the widget for the given field name to the given (model) value.
        This will also update the current model and validate it.
        """
        value = getattr(self._current_item, field_name)

        if widget_type == 'modelselect':
            item_type = self._fields[field_name].item_type
            assert item_type is not None, f"item_type for field '{field_name}' must not be None"
            repository = self._model_repositories[item_type.__name__]
            if not repository:
                raise ValueError(f"Model repository for {item_type.__name__} not found in form's model repositories")
            value = repository.key_from_item(value)

        elif type(value) is datetime.datetime:
            tz = ZoneInfo(self.local_tz) if self.local_tz else None
            value = value.astimezone(tz).replace(tzinfo=None).isoformat()
        
        elif widget_type == 'timedelta':
            timedelta_adapter = TypeAdapter(datetime.timedelta)
            value = timedelta_adapter.dump_python(value, mode="json")

        widget.value = value  # type: ignore[attr-defined]

        return self


    def _from_widget_value_to_current_item(self, field_name: str) -> None:
        """
        Convert the value from the widget to the model value.
        Exceptions should be handled by the caller.
        """
        # determine the widget
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
                value = float(value)  # convert to float for number fields

        elif widget_type == 'ui.input_chips':
            # split comma separated values
            for v in value:
                if isinstance(v, str) and ',' in v:
                    value.remove(v)
                    value.extend([item.strip() for item in v.split(',')])

        # convert the value depending on the widget type
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
            repository = self._model_repositories[item_type.__name__]
            if not repository:
                raise ValueError(f"Model repository for {item_type.__name__} not found in form's model repositories")
            value = repository.read(value)

        setattr(self._current_item, field_name, value)


    def _validation_errors(self, field_name: str, value) -> str | None:
        return self._validation_error_messages.get(field_name, None)


    def _validate(self, field_name: str | None = None) -> None:
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


    def has_validation_errors(self) -> bool:
        return bool(self._validation_error_messages) or bool(self._nonfield_validation_errors)


    def _handle_blur_event(self, field_name: str, event) -> None:
        vce = ValueChangeEventArguments(sender=event.sender, client=event.client, value=event.sender.value)
        self._handle_value_change(field_name, vce)


    def _handle_validate(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        old_value = getattr(self._current_item, field_name)
        new_value = value_change_event.sender.value  # type: ignore[attr-defined]

        if old_value != new_value:
            error_msg = None
            try:
                self._from_widget_value_to_current_item(field_name)
            except Exception as e:
                error_msg = f"Error interpreting widget value"

            self._validate()

            # reflect previous conversion errors in the validation error message
            if error_msg is not None:
                self._validation_error_messages[field_name] = error_msg


    def _handle_value_change(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        # do not handle the change event if the validation failed because of this field
        if len(self._validation_error_messages.get(field_name, '')) > 0:
            return

        # do not handle non-changes
        old_value = getattr(self._validated_item, field_name)
        new_value = getattr(self._current_item, field_name)
        if old_value == new_value:
            return

        setattr(self._validated_item, field_name, new_value)

        # handle autosave (only if a model adapter is set; with from_item the item is already modified in-place)
        if self.autosave and self._item_model is not None:
            self._save()

        # call the change handlers
        #event.args.update({'field_name': field_name, 'old_value': old_value, 'new_value': new_value})
        #value_change_event = ValueChangeEventArguments(sender=event.sender, client=event.client, value=event.value)
        fce = FieldChangeEventArguments(
            sender=value_change_event.sender,
            client=value_change_event.client,
            form=self,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
        )
        for handler in self._change_handlers:
            handle_event(handler, fce)


    def _handle_validate_and_change(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        self._handle_validate(field_name, value_change_event)
        self._handle_value_change(field_name, value_change_event)
