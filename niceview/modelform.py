from dataclasses import dataclass
import datetime
from typing import Any, List, Self, Unpack
import typing
from zoneinfo import ZoneInfo
import typing_extensions
from pydantic import BaseModel, ValidationError

from nicegui import ui
from nicegui.events import Handler, UiEventArguments, ValueChangeEventArguments, handle_event
from nicegui.dataclasses import KWONLY_SLOTS

from niceview.dataadapter import ModelDataAdapter, SqlModelAdapter
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
    """Whether to automatically save the form when the value changes. Defaults to False."""
    on_change: Handler[FieldChangeEventArguments]
    """Callback to execute when value changes. To reduce the number of change events, fields like ui.input or ui.number also have to loose focus (blur)."""

class ModelForm():
    """
    A form class that can be used to create forms for Pydantic models.
    Configuration options can be defined in the item's Meta class, 
    or as keyword arguments when creating the form.
    """
    _item_type: type[BaseModel]
    _item_model: ModelDataAdapter | None
    _item_key: str | int | None
    _model_repositories: dict[str, ModelDataAdapter]
    _autosave: bool = False
    _change_handler: Handler[FieldChangeEventArguments]

    _fields: Fields
    _current_item: BaseModel | None
    _validated_item: BaseModel | None
    _validation_error_messages: dict[str, str]
    widgets: dict[str, ui.element]

    title: str
    description: str
    classes: str
    tailwind: str
    style: str
    props: str


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
            value = kwargs.pop(param, value)  # override with kwargs if provided
            return value
        
        if not isinstance(item_type, type) or not issubclass(item_type, BaseModel):
            raise TypeError(f"item_type must be a subclass of BaseModel, got {item_type}")

        self._item_type = item_type
        self._item_model = None
        self._item_key = None
        self._model_repositories = {}
        self._autosave = _get_param('autosave', False)
        self._change_handlers = []

        include = _get_param('include', '__all__')
        exclude = _get_param('exclude', '')
        field_info = _get_param('field_info', {})
        self._fields = Fields(item_type, include, exclude, field_info)
        self._current_item = None
        self._validated_item = None
        self._validation_error_messages = {}
        self.widgets = {}

        self.title = _get_param('title', '')
        self.description = _get_param('description', '')
        self.classes = _get_param('classes', '')
        self.tailwind = _get_param('tailwind', '')
        self.style = _get_param('style', '')
        self.props = _get_param('props', '')

        if on_change_callback := kwargs.pop('on_change', None):
            self.on_change(on_change_callback)

        if len(kwargs) > 0:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(kwargs.keys())}")


    @classmethod
    def from_item(cls, item: BaseModel, **kwargs: Unpack[_ModelFormOptionInputs]) -> Self:
        """
        Create a ModelForm instance from a BaseModel item.
        """
        if not isinstance(item, BaseModel):
            raise TypeError(f"item must be a BaseModel instance, got {type(item)}")
        ret = cls(type(item), **kwargs)
        ret.item = item
        return ret


    @property
    def item(self) -> BaseModel:
        """
        Get the current (validated) item of the form.
        This is the item that is currently being edited.
        """
        if not self._validated_item:
            raise ValueError("No current item set. Use set_item() to set the current item.")
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


    def set_item_from_model(self, item_model: ModelDataAdapter, item_key: str | int) -> Self:
        """
        Set the form's (validated) item for editing.
        Editing the form will modify this item directly.
        """
        self._item_model = item_model
        self._item_key = item_key
        item = self._item_model.read(item_key)
        if not isinstance(item, BaseModel):
            raise TypeError(f"item must be a BaseModel instance, got {type(item)}")
        self.item = item
        return self
    
    def set_model_repositories(self, repositories: dict[str, ModelDataAdapter]) -> Self:
        """
        Set the model repositories for the form.
        This is a dictionary of model data adapters that can be used to read and write items.
        """
        if not isinstance(repositories, dict):
            raise TypeError(f"model_repositories must be a dictionary, got {type(dict)}")
        self._model_repositories = repositories
        return self


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
            widget = EditGridWrapper(widget, title=field_info.label)
            widget.on_change(notify_change)
            widget.render()
        else:  # create a read-only grid for the field
            ui.label(field_info.label).classes('text-h6')
            widget.render()
        return widget


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
        widget = None

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
            widget.tailwind(self.tailwind)
            widget.style(self.style)
            widget.props(self.props)

        return widget


    def render(self) -> Self:
        """
        Render the form
        """
        if self.title:
            ui.label(self.title).classes('text-h4')
        if self.description:
            ui.label(self.description)

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

        return self


    def _from_current_item_to_widget_value(self, field_name: str, widget_type: str, widget) -> Self:
        """
        Set the value of the widget for the given field name to the given (model) value.
        This will also update the current model and validate it.
        """
        value = getattr(self._current_item, field_name)

        if widget_type == 'modelselect':
            repository = self._model_repositories[self._fields[field_name].item_type.__name__]
            if not repository:
                raise ValueError(f"Model repository for {self._fields[field_name].item_type.__name__} not found in form's model repositories")
            value = repository.key_from_item(value)

        elif type(value) is datetime.datetime:
            # timezone support for datetime fields
            local_tz = ZoneInfo("Europe/Berlin")  #TODO: remove hardcoded timezone
            value = value.astimezone(local_tz).replace(tzinfo=None).isoformat()

        widget.value = value

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
        value = widget.value

        # convert the value depending on the widget type
        if widget_type == 'datetime':
            dt = datetime.datetime.fromisoformat(value)
            local_tz = ZoneInfo("Europe/Berlin")  #TODO: remove hardcoded timezone
            value = dt.replace(tzinfo=local_tz)
            value = value.astimezone(datetime.timezone.utc)  # convert to UTC

        elif widget_type == 'ui.input' and typing.get_origin(field_type) == list:
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

        elif widget_type == 'modelselect':
            repository = self._model_repositories[self._fields[field_name].item_type.__name__]
            if not repository:
                raise ValueError(f"Model repository for {self._fields[field_name].item_type.__name__} not found in form's model repositories")
            value = repository.read(value)

        setattr(self._current_item, field_name, value)


    def _validation_errors(self, field_name: str, value) -> str | None:
        # return validation error messages for the field
        msg = self._validation_error_messages.get(field_name, None)
        #print(f"_validation_errors: Validation error for field {field_name}: {msg}")
        return msg


    def _validate(self, field_name: str | None = None) -> None:
        field_errors, nonfield_errors = self._fields.validation_errors(self._current_item.model_dump())
        self._validation_error_messages = field_errors
        # TODO find a way to display the validation errors in the UI


    def _handle_blur_event(self, field_name: str, event) -> None:
        """
        Handle the change event to update the model with the new value.
        """
        #print(f"change '{field_name}': {event}")
        # GenericEventArguments(sender=<nicegui.elements.number.Number object at 0x113dcec10>, client=<nicegui.client.Client object at 0x113d27cb0>, 
        #  args={'isTrusted': True, '_vts': 1747817122891, 'detail': 0, 'layerX': 0, 'layerY': 0, 'pageX': 0, 'pageY': 0, 
        #   'which': 0, 'type': 'focusout', 'currentTarget': None, 'eventPhase': 0, 'cancelBubble': False, 
        #   'bubbles': True, 'cancelable': False, 'defaultPrevented': False, 'composed': True, 'timeStamp': 8820, 
        #   'returnValue': True, 'NONE': 0, 'CAPTURING_PHASE': 1, 'AT_TARGET': 2, 'BUBBLING_PHASE': 3})
        vce = ValueChangeEventArguments(sender=event.sender, client=event.client, value=event.sender.value)
        self._handle_value_change(field_name, vce)


    def _handle_validate(self, field_name: str, value_change_event: ValueChangeEventArguments) -> None:
        old_value = getattr(self._current_item, field_name)
        new_value = value_change_event.sender.value

        if old_value != new_value:
            # update the current model from the widget & validate the current model
            #print(f"_handle_validate field_name={field_name} event={value_change_event}: old_value={old_value} new_value={new_value}")
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
            # validation error, do not update the model
            #print(f"_handle_value_change field_name={field_name} event={value_change_event}: change not accepted or propagated, validation error(s): {self._validation_error_messages}")
            return

        # do not handle non-changes
        old_value = getattr(self._validated_item, field_name)
        new_value = getattr(self._current_item, field_name)
        if old_value == new_value:
            return

        # change accepted, update teh validated model from the current model
        #print(f"_handle_value_change field_name={field_name} event={value_change_event}: old_value={old_value} new_value={new_value}")
        setattr(self._validated_item, field_name, new_value)

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
