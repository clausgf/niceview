import datetime
import logging
import typing

import pydantic
import sqlalchemy
from sqlmodel import SQLModel, Relationship
from niceview.fieldinfo import FieldInfo
import importlib

log = logging.getLogger('niceview')


class Fields(typing.Mapping[str, FieldInfo]):
    """
    Fields and field information for datamodel based UI components.
    """
    _item_type: type[pydantic.BaseModel]
    _include: list[str]
    _exclude: list[str]
    _field_names: list[str]
    _field_infos: dict[str, FieldInfo]
    _widget_lookup: dict[type, str] = {
        str: 'ui.input',
        int: 'ui.number',
        float: 'ui.number',
        bool: 'ui.switch',
        datetime.datetime: 'datetime',
        datetime.date: 'date',
        datetime.time: 'time',
    }


    def is_included(self, field_name: str) -> bool:
        """
        Check if the field is included (and not excluded) in the fields.
        """
        if field_name.startswith('_'):
            return False
        if self._include == ['__all__']:
            return field_name not in self._exclude

        return field_name in self._include and field_name not in self._exclude


    def __init__(self, item_type: type[pydantic.BaseModel], include: str | typing.Iterable[str] = '__all__', exclude: str | typing.Iterable[str] = '', field_infos: dict[str, FieldInfo] = {}):

        def _parse_field_names(field_list: str | typing.Iterable[str], all_fields: set[str], allow_all: bool) -> list[str]:
            """Parse a include or exclude list of fields from a string or iterable."""
            if isinstance(field_list, str):
                result = [f.strip() for f in field_list.split(',') if f.strip()]
            elif isinstance(field_list, typing.Iterable):
                result = list(field_list)
            else:
                raise ValueError(f"Invalid field list: '{field_list}' must be a string or an iterable of field names")

            if allow_all and result == ['__all__']:
                return ['__all__']

            invalid = [f for f in result if not isinstance(f, str) or f not in all_fields]
            if invalid:
                raise ValueError(f"Invalid field name(s): {invalid} not found in '{self._item_type.__name__}'")

            return result

        self._item_type = item_type
        self._include = _parse_field_names(include, set(item_type.model_fields.keys()), allow_all=True)
        self._exclude = _parse_field_names(exclude, set(item_type.model_fields.keys()), allow_all=False)
        self._field_names = []
        self._field_infos = {}

        pydantic_fields = item_type.model_fields
        print(self._item_type)
        is_sqlmodel = issubclass(self._item_type, SQLModel)
        for field_name, field_type in self._item_type.__annotations__.items():
            field_info = None
            if not self.is_included(field_name):
                continue  # skip fields that are not included or are excluded

            # lowest priority: determine field info from the pydantic model
            if field_name in pydantic_fields:
                # If the field is already defined in the Pydantic model, we can use its metadata
                field_info = self._field_info_from_pydantic(field_name, pydantic_fields[field_name])

            elif is_sqlmodel:
                # If the field is a SQLModel relationship, we can create a FieldInfo for it
                field_info = self._field_info_from_sqlmodel(field_name, field_type)

            if field_info:
                self._field_names.append(field_name)
                self._field_infos[field_name] = field_info

            # scan for a Meta class with additional niceview.fieldinfo for this field
            meta = getattr(self._item_type, 'Meta', None)
            if meta is not None:
                meta_field_info = getattr(meta, 'field_info', {})
                if isinstance(meta_field_info, dict) and field_name in meta_field_info:
                    # merge the field info from the Meta class with the field info from the model
                    fi = meta_field_info[field_name]
                    if isinstance(fi, FieldInfo):
                        self._field_infos[field_name] = FieldInfo(**{**self._field_infos[field_name], **fi}) # type: ignore
                    else:
                        raise ValueError(f"Invalid field info in Meta class for field '{field_name}': {field_info}")

            # overwrite field info gathered so far with the FieldInfo provided
            if field_name in field_infos:
                field_info_arg = field_infos[field_name]
                self._field_infos[field_name] = FieldInfo(**{**self._field_infos[field_name], **field_info_arg}) # type: ignore

            if field_name in self._field_infos:
                log.debug(f"{self._item_type.__name__}.{field_name} type={field_type} FieldInfo={self._field_infos[field_name]}")
            else:
                log.debug(f"{self._item_type.__name__}.{field_name} type={field_type} has no additional info")


    def _label_from_name(self, name: str) -> str:
        """
        Convert a field name to a more user-friendly format.
        """
        return name.replace('_', ' ').capitalize()


    def _field_info_from_pydantic(self, field_name: str, py_field_info: pydantic.fields.FieldInfo) -> FieldInfo:
        """
        Create a field info for the given field name.
        """
        field_type = py_field_info.annotation
        if field_type is None:
            raise ValueError(f"Field '{field_name}' has no type annotation")

        # check for FieldInfo annotation
        nv_field_info = None
        for i in py_field_info.metadata:
            if isinstance(i, FieldInfo):
                nv_field_info = i
        if nv_field_info is None:
            nv_field_info = FieldInfo()

        nv_field_info.field_type = field_type

        # determine widget type from field type
        if nv_field_info.widget_type is None:
            # remove the Optional from a type
            if typing.get_origin(field_type) is typing.Union:
                # if the field type is a Union, get the first non-None type
                union_types = next((t for t in typing.get_args(field_type) if t is not type(None)), None)
                if len(union_types) == 1: # type: ignore
                    field_type = union_types[0] # type: ignore

            if field_type in self._widget_lookup:
                nv_field_info.widget_type = self._widget_lookup[field_type] # type: ignore

            elif typing.get_origin(field_type) == typing.Literal:
                nv_field_info.widget_type = 'ui.select'
                if nv_field_info.select_options is None:
                    nv_field_info.select_options = list(typing.get_args(field_type))

            elif typing.get_origin(field_type) == list:
                if nv_field_info.item_type is None:
                    for arg in typing.get_args(field_type):
                        if isinstance(arg, type) and (
                            issubclass(arg, pydantic.BaseModel) or arg in (int, float, bool, str)
                        ):
                            nv_field_info.item_type = arg
                            break
                if nv_field_info.item_type is None:
                    raise ValueError(f"Field '{field_name}' is a list but no item type is specified in FieldInfo or as a pydantic model type")
                elif issubclass(nv_field_info.item_type, pydantic.BaseModel):
                    nv_field_info.widget_type = 'editgrid'
                else:
                    nv_field_info.widget_type = 'ui.input'

            else:
                nv_field_info.widget_type = 'ui.input'  # default widget type if not specified

        # merge regular field info with FieldInfo
        if not nv_field_info.label and py_field_info.title:
            nv_field_info.label = py_field_info.title
        if not nv_field_info.label:
            nv_field_info.label = self._label_from_name(field_name)
        if nv_field_info.placeholder is None:
            nv_field_info.placeholder = py_field_info.description
        if nv_field_info.required is None:
            nv_field_info.required = py_field_info.is_required()
        if nv_field_info.tooltip is None:
            nv_field_info.tooltip = py_field_info.description

        # merge regular aditional metadata with FieldInfo min/max/step
        if field_type in (int, float):
            meta = py_field_info.metadata
            if not nv_field_info.min and hasattr(meta, 'gt'):
                nv_field_info.min = py_field_info.gt
            elif not nv_field_info.min and hasattr(meta, 'ge'):
                nv_field_info.min = py_field_info.ge
            if not nv_field_info.max and hasattr(meta, 'lt'):
                nv_field_info.max = py_field_info.lt
            elif not nv_field_info.max and hasattr(meta, 'le'):
                nv_field_info.max = py_field_info.le
            if not nv_field_info.step and hasattr(meta, 'multiple_of'):
                nv_field_info.step = py_field_info.multiple_of
        
        return nv_field_info
    

    def _field_info_from_sqlmodel(self, field_name: str, field_type: type) -> FieldInfo | None:
        """
        Return a field info generated from the given SQLModel field name or None.
        """
        field_info = None # no field info by default
        origin = typing.get_origin(field_type)
        args = typing.get_args(field_type)

        # Check if it is a Relationship (type changed to Mapped)
        if not origin or not issubclass(origin, sqlalchemy.orm.Mapped): # type: ignore
            return None  # Skip if not a Mapped type

        # This is a Mapped type, get the actual relationship type
        for mapping_type in args:
            rel_origin = typing.get_origin(mapping_type)
            rel_args = typing.get_args(mapping_type)

            if rel_origin and rel_origin == list and rel_args:
                # list of relationships (one-to-many or many-to-many)
                if len(rel_args) != 1:
                    raise ValueError(f"Field '{field_name}' is a list but has more than one type specified in FieldInfo or as a pydantic model type")
                other_type = rel_args[0]
                # normalize other_type
                if isinstance(other_type, str):
                    # Try to resolve the class from the global namespace of the model class
                    import sys
                    module = getattr(self._item_type, '__module__', None)
                    resolved_type = None
                    if module and module in sys.modules:
                        mod = sys.modules[module]
                        resolved_type = getattr(mod, other_type, None)
                    if resolved_type is None:
                        # Fallback: try to import the module and get the type
                        if module:
                            mod = importlib.import_module(module)
                            resolved_type = getattr(mod, other_type, None)
                    if resolved_type is None or not isinstance(resolved_type, type):
                        raise ValueError(f"Cannot resolve type '{other_type}' for field '{field_name}'")
                    other_type = resolved_type
                log.debug(f"Resolving sqlmodel {other_type=} (MRO: {getattr(other_type, '__mro__', None)})")
                if other_type is None or not issubclass(other_type, pydantic.BaseModel):
                    raise ValueError(f"Field '{field_name}' is a list but no item type is specified in FieldInfo or as a pydantic model type")
                # create a FieldInfo for an editgrid
                field_info = FieldInfo(
                    label=self._label_from_name(field_name),
                    widget_type='editgrid',
                    item_type=other_type,  # type: ignore
                )
                field_info.field_type = mapping_type
            else:
                # single relationship (one-to-one or many-to-one)
                other_type = mapping_type
                field_info = FieldInfo(
                    label=self._label_from_name(field_name),
                    widget_type='modelselect',  # use modelselect for single relationships
                    with_input=True,  # allow input to search the select widget
                    #select_options=lambda: [i.model_dump() for i in other_type.query()],
                    item_type=other_type,  # type: ignore
                )
                field_info.field_type = mapping_type

        return field_info


    @property
    def field_names(self) -> typing.Iterable[str]:
        """
        Get the field names of the model.
        """
        return self._field_names


    def __getitem__(self, key: str) -> FieldInfo:
        """
        Get the field information for the given field name.
        """
        return self._field_infos[key]
    
    def __iter__(self) -> typing.Iterator[str]:
        """
        Iterate over the field names of the model.
        """
        return iter(self._field_names)
    
    def __len__(self) -> int:
        """
        Get the number of fields in the model.
        """
        return len(self._field_names)


    def validation_errors(self, model_dict) -> typing.Tuple[typing.Dict[str, str], typing.List[str]]:
        """
        Validate the model with the new value and return a list of validation errors.
        If there are no validation errors, return None.
        """
        field_errors = {}
        nonfield_errors = []
        try:
            # validate the model
            self._item_type.model_validate(model_dict)
        except pydantic.ValidationError as e:
            for error in e.errors():
                error_was_handled = False
                # check if the error can be attributed to a known field
                for loc in error['loc']:
                    if loc in self._field_names:
                        field_name = loc
                        if field_name not in field_errors:
                            field_errors[field_name] = []
                        field_errors[field_name].append(error['msg'])
                        error_was_handled = True
                if not error_was_handled:
                    # if the error cannot be attributed to a known field, it is a non-field error
                    nonfield_errors.append(error['msg'])
        for k, v in field_errors.items():
            field_errors[k] = ', '.join(v)
        return field_errors, nonfield_errors


    def validation_error_list(self, model_dict) -> typing.List[str]:
        """
        Validate the model with the new value and return a list of validation error messages.
        """
        field_errors, nonfield_errors = self.validation_errors(model_dict)

        # collect the validation error messages
        errors = []
        for k, v in field_errors.items():
            field_label = self._field_infos[k].label or k
            errors.append(f"{field_label}: {v}")
        errors.extend(nonfield_errors)
        return errors
