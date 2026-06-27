import datetime
import logging
import sys
import types
import typing
import importlib

import annotated_types
import pydantic
import sqlalchemy
from sqlmodel import SQLModel
from niceview.fieldinfo import FieldInfo, _merge_field_infos

log = logging.getLogger('niceview')


class _FieldInfoResolver:
    """Converts a single Pydantic or SQLModel field annotation to a niceview FieldInfo."""

    _widget_lookup: dict[type, str] = {
        str: 'ui.input',
        int: 'ui.number',
        float: 'ui.number',
        bool: 'ui.switch',
        datetime.datetime: 'datetime',
        datetime.date: 'date',
        datetime.time: 'time',
        datetime.timedelta: 'timedelta',
    }

    def __init__(self, item_type: type[pydantic.BaseModel]):
        self._item_type = item_type

    def from_pydantic(self, field_name: str, py_field_info: pydantic.fields.FieldInfo) -> FieldInfo:
        log.debug(f"_field_info_from_pydantic: {field_name=} annotation={py_field_info.annotation} metadata={py_field_info.metadata}")

        field_type = py_field_info.annotation
        if field_type is None:
            raise ValueError(f"Field '{field_name}' has no type annotation")

        nv_field_info = next((i for i in py_field_info.metadata if isinstance(i, FieldInfo)), FieldInfo())
        log.debug(f"_field_info_from_pydantic: {field_name=} nv_field_info from metadata: {vars(nv_field_info)}")

        nv_field_info.field_type = field_type

        if typing.get_origin(field_type) == typing.Literal:
            nv_field_info.literal_options = list(typing.get_args(field_type))
            log.debug(f"_field_info_from_pydantic: {field_name=} Literal options: {nv_field_info.literal_options}")

        if nv_field_info.widget_type is None:
            self._infer_widget_type(field_name, field_type, nv_field_info)
        else:
            log.debug(f"_field_info_from_pydantic: {field_name=} widget_type already set: {nv_field_info.widget_type}")

        self._apply_pydantic_metadata(field_name, nv_field_info, py_field_info)

        log.debug(f"_field_info_from_pydantic: {field_name=} result: widget_type={nv_field_info.widget_type} label={nv_field_info.label!r} required={nv_field_info.required} min={nv_field_info.min} max={nv_field_info.max} step={nv_field_info.step}")
        return nv_field_info

    def from_sqlmodel(self, field_name: str, field_type: type) -> FieldInfo | None:
        origin = typing.get_origin(field_type)
        args = typing.get_args(field_type)

        if not origin or not issubclass(origin, sqlalchemy.orm.Mapped):  # type: ignore
            return None

        field_info = None
        for mapping_type in args:
            rel_origin = typing.get_origin(mapping_type)
            rel_args = typing.get_args(mapping_type)

            if rel_origin and rel_origin == list and rel_args:
                if len(rel_args) != 1:
                    raise ValueError(f"Field '{field_name}' is a list but has more than one type specified in FieldInfo or as a pydantic model type")
                other_type = rel_args[0]
                if isinstance(other_type, str):
                    other_type = self._resolve_type_string(other_type, field_name)
                log.debug(f"Resolving sqlmodel {other_type=} (MRO: {getattr(other_type, '__mro__', None)})")
                if not issubclass(other_type, pydantic.BaseModel):
                    raise ValueError(f"Field '{field_name}' is a list but no item type is specified in FieldInfo or as a pydantic model type")
                field_info = FieldInfo(
                    label=self._label_from_name(field_name),
                    widget_type='editgrid',
                    item_type=other_type,  # type: ignore
                )
                field_info.field_type = mapping_type
            else:
                other_type = mapping_type
                field_info = FieldInfo(
                    label=self._label_from_name(field_name),
                    widget_type='modelselect',
                    with_input=True,
                    item_type=other_type,  # type: ignore
                )
                field_info.field_type = mapping_type

        return field_info

    def _label_from_name(self, name: str) -> str:
        return name.replace('_', ' ').capitalize()

    def _infer_widget_type(self, field_name: str, field_type: type, nv_field_info: FieldInfo) -> None:
        if typing.get_origin(field_type) is typing.Union or isinstance(field_type, types.UnionType):
            union_types = [t for t in typing.get_args(field_type) if t is not type(None)]
            if len(union_types) == 1:
                field_type = union_types[0]
                log.debug(f"_field_info_from_pydantic: {field_name=} unwrapped Optional -> {field_type}")
            else:
                log.warning(f"Field '{field_name}' has a Union type with multiple non-None types, cannot determine widget type: {field_type=} {union_types=}")

        if field_type in self._widget_lookup:
            nv_field_info.widget_type = self._widget_lookup[field_type]
            log.debug(f"_field_info_from_pydantic: {field_name=} widget_type from lookup: {nv_field_info.widget_type}")
        elif typing.get_origin(field_type) == typing.Literal:
            nv_field_info.widget_type = 'ui.select'
            if nv_field_info.select_options is None:
                nv_field_info.select_options = list(typing.get_args(field_type))
            log.debug(f"_field_info_from_pydantic: {field_name=} widget_type=ui.select select_options={nv_field_info.select_options}")
        elif typing.get_origin(field_type) == list:
            self._infer_list_widget_type(field_name, field_type, nv_field_info)
        else:
            nv_field_info.widget_type = 'ui.input'
            log.debug(f"_field_info_from_pydantic: {field_name=} unrecognised type {field_type}, defaulting widget_type=ui.input")

    def _infer_list_widget_type(self, field_name: str, field_type: type, nv_field_info: FieldInfo) -> None:
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
        elif issubclass(nv_field_info.item_type, str):
            nv_field_info.widget_type = 'ui.input_chips'
        else:
            nv_field_info.widget_type = 'ui.input'
        log.debug(f"_field_info_from_pydantic: {field_name=} list field -> widget_type={nv_field_info.widget_type} item_type={nv_field_info.item_type}")

    def _apply_pydantic_metadata(self, field_name: str, nv_field_info: FieldInfo, py_field_info: pydantic.fields.FieldInfo) -> None:
        if not nv_field_info.label:
            nv_field_info.label = py_field_info.title or self._label_from_name(field_name)
        if nv_field_info.placeholder is None:
            nv_field_info.placeholder = py_field_info.description
        if nv_field_info.required is None:
            nv_field_info.required = py_field_info.is_required()
        if nv_field_info.tooltip is None:
            nv_field_info.tooltip = py_field_info.description

        # unwrap Optional to check for numeric constraints (e.g. int | None still needs min/max)
        effective_type = nv_field_info.field_type
        if typing.get_origin(effective_type) is typing.Union or isinstance(effective_type, types.UnionType):
            non_none = [t for t in typing.get_args(effective_type) if t is not type(None)]
            if len(non_none) == 1:
                effective_type = non_none[0]

        if effective_type in (int, float):
            for constraint in py_field_info.metadata:
                if nv_field_info.min is None and isinstance(constraint, annotated_types.Gt):
                    nv_field_info.min = float(constraint.gt)  # type: ignore[arg-type]
                elif nv_field_info.min is None and isinstance(constraint, annotated_types.Ge):
                    nv_field_info.min = float(constraint.ge)  # type: ignore[arg-type]
                if nv_field_info.max is None and isinstance(constraint, annotated_types.Lt):
                    nv_field_info.max = float(constraint.lt)  # type: ignore[arg-type]
                elif nv_field_info.max is None and isinstance(constraint, annotated_types.Le):
                    nv_field_info.max = float(constraint.le)  # type: ignore[arg-type]
                if nv_field_info.step is None and isinstance(constraint, annotated_types.MultipleOf):
                    nv_field_info.step = float(constraint.multiple_of)  # type: ignore[arg-type]

    def _resolve_type_string(self, type_str: str, field_name: str) -> type:
        """Resolve a forward-reference string to its class, using the model's module."""
        module = getattr(self._item_type, '__module__', None)
        resolved = None
        if module:
            mod = sys.modules.get(module) or importlib.import_module(module)
            resolved = getattr(mod, type_str, None)
        if resolved is None or not isinstance(resolved, type):
            raise ValueError(f"Cannot resolve type '{type_str}' for field '{field_name}'")
        return resolved


class Fields(typing.Mapping[str, FieldInfo]):
    """
    Fields and field information for datamodel based UI components.
    """
    _item_type: type[pydantic.BaseModel]
    _include: list[str]
    _exclude: list[str]
    _field_names: list[str]
    _field_infos: dict[str, FieldInfo]

    def __init__(self, item_type: type[pydantic.BaseModel], include: str | typing.Iterable[str] = '__all__', exclude: str | typing.Iterable[str] = '', field_infos: dict[str, FieldInfo] = {}, profile: str | None = None):
        self._item_type = item_type
        meta = getattr(item_type, 'Meta', None)

        if profile is not None:
            profiles: dict = getattr(meta, 'profiles', {}) if meta else {}
            if profile not in profiles:
                available = list(profiles.keys())
                raise ValueError(f"Profile '{profile}' not found in {item_type.__name__}.Meta.profiles. Available: {available}")
            include = profiles[profile]

        all_fields = set(item_type.model_fields.keys())
        self._include = self._parse_field_names(include, all_fields, allow_all=True, model_name=item_type.__name__)
        self._exclude = self._parse_field_names(exclude, all_fields, allow_all=False, model_name=item_type.__name__)

        resolver = _FieldInfoResolver(item_type)
        self._field_names, self._field_infos = self._build_field_infos(resolver, meta, field_infos)
        self._apply_field_order(meta)

    @staticmethod
    def _parse_field_names(field_list: str | typing.Iterable[str], all_fields: set[str], *, allow_all: bool, model_name: str = '') -> list[str]:
        """Parse an include or exclude field list from a string or iterable."""
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
            raise ValueError(f"Invalid field name(s): {invalid} not found in '{model_name}'")

        return result

    def is_included(self, field_name: str) -> bool:
        """
        Check if the field is included (and not excluded) in the fields.
        Exclude private fields (starting with '_') by default.
        """
        if field_name.startswith('_'):
            return False
        if self._include == ['__all__']:
            return field_name not in self._exclude
        return field_name in self._include and field_name not in self._exclude

    def _build_field_infos(self, resolver: _FieldInfoResolver, meta, field_infos: dict[str, FieldInfo]) -> tuple[list[str], dict[str, FieldInfo]]:
        pydantic_fields = self._item_type.model_fields
        is_sqlmodel = issubclass(self._item_type, SQLModel)
        meta_field_info: dict[str, FieldInfo] = getattr(meta, 'field_info', {}) if meta is not None else {}

        names: list[str] = []
        infos: dict[str, FieldInfo] = {}

        for field_name, field_type in self._item_type.__annotations__.items():
            if not self.is_included(field_name):
                continue

            if field_name in pydantic_fields:
                fi = resolver.from_pydantic(field_name, pydantic_fields[field_name])
            elif is_sqlmodel:
                fi = resolver.from_sqlmodel(field_name, field_type)
            else:
                fi = None

            if fi is None:
                log.debug(f"{self._item_type.__name__}.{field_name} type={field_type} has no additional info")
                continue

            if field_name in meta_field_info:
                meta_fi = meta_field_info[field_name]
                if not isinstance(meta_fi, FieldInfo):
                    raise ValueError(f"Invalid field info in Meta class for field '{field_name}': {meta_fi}")
                fi = _merge_field_infos(fi, meta_fi)

            if field_name in field_infos:
                fi = _merge_field_infos(fi, field_infos[field_name])

            names.append(field_name)
            infos[field_name] = fi
            log.debug(f"{self._item_type.__name__}.{field_name} type={field_type} FieldInfo={fi}")

        return names, infos

    def _apply_field_order(self, meta) -> None:
        field_order: list[str] | None = getattr(meta, 'field_order', None) if meta is not None else None
        if field_order is None:
            return

        unknown = [f for f in field_order if f not in self._field_infos]
        if unknown:
            raise ValueError(f"Meta.field_order contains unknown field(s) for '{self._item_type.__name__}': {unknown}")

        ordered = [f for f in field_order if f in self._field_names]
        remaining = [f for f in self._field_names if f not in set(field_order)]
        self._field_names = ordered + remaining
        log.debug(f"{self._item_type.__name__}: field_order applied -> {self._field_names}")

    @property
    def field_names(self) -> typing.Iterable[str]:
        return self._field_names

    def __getitem__(self, key: str) -> FieldInfo:
        return self._field_infos[key]

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self._field_names)

    def __len__(self) -> int:
        return len(self._field_names)

    def validation_errors(self, model_dict) -> typing.Tuple[typing.Dict[str, str], typing.List[str]]:
        """
        Validate the model with the new value and return a list of validation errors.
        If there are no validation errors, return None.
        """
        field_error_lists: dict[str, list[str]] = {}
        nonfield_errors: list[str] = []
        try:
            self._item_type.model_validate(model_dict)
        except pydantic.ValidationError as e:
            for error in e.errors():
                msg = error['msg']
                attributed = False

                # First pass: find a visible (non-hidden) field in the error location
                for loc in error['loc']:
                    if not isinstance(loc, str) or loc not in self._field_names:
                        continue
                    if not self._field_infos[loc].hidden:
                        field_error_lists.setdefault(loc, []).append(msg)
                        attributed = True
                        break

                if not attributed:
                    # Second pass: find a hidden field, redirect FK errors to the visible relationship field
                    for loc in error['loc']:
                        if not isinstance(loc, str) or loc not in self._field_names:
                            continue
                        fi = self._field_infos[loc]
                        if not fi.hidden:
                            continue
                        # e.g. author_id -> author
                        base = loc.removesuffix('_id') if loc.endswith('_id') else None
                        if base and base in self._field_names and not self._field_infos[base].hidden:
                            field_error_lists.setdefault(base, []).append(msg)
                        else:
                            nonfield_errors.append(f"{fi.label or loc}: {msg}")
                        attributed = True
                        break

                if not attributed:
                    nonfield_errors.append(msg)

        field_errors: dict[str, str] = {k: ', '.join(v) for k, v in field_error_lists.items()}
        return field_errors, nonfield_errors

    def validation_error_list(self, model_dict) -> typing.List[str]:
        """
        Validate the model with the new value and return a list of validation error messages.
        """
        field_errors, nonfield_errors = self.validation_errors(model_dict)
        errors = []
        for k, v in field_errors.items():
            field_label = self._field_infos[k].label or k
            errors.append(f"{field_label}: {v}")
        errors.extend(nonfield_errors)
        return errors
