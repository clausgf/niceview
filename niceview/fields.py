import dataclasses
import datetime
import enum
import logging
import sys
import types
import typing
import importlib

import annotated_types
import pydantic
from niceview.fieldinfo import FieldInfo, WidgetType, _merge_field_infos

try:
    import sqlalchemy  # noqa: F401  # availability probe: sqlmodel requires sqlalchemy
    from sqlmodel import SQLModel as _SQLModel
    _SQLMODEL_AVAILABLE = True
except ImportError:
    _SQLModel = None  # type: ignore[assignment,misc]
    _SQLMODEL_AVAILABLE = False

log = logging.getLogger('niceview')


class _FieldInfoResolver:
    """Converts a single Pydantic or SQLModel field annotation to a niceview FieldInfo."""

    _widget_lookup: dict[type, WidgetType] = {
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

        # Copy the FieldInfo found in the Annotated metadata: it is attached to the model
        # class and shared by every Fields/form/grid instance — mutating it would leak
        # resolved state (labels, widget types, select options) across instances.
        found = next((i for i in py_field_info.metadata if isinstance(i, FieldInfo)), None)
        nv_field_info = _merge_field_infos(found, FieldInfo()) if found is not None else FieldInfo()
        log.debug(f"_field_info_from_pydantic: {field_name=} nv_field_info from metadata: {vars(nv_field_info)}")

        nv_field_info.field_type = field_type

        # Extract Literal options for both Literal[...] and list[Literal[...]] (Optional-unwrapped)
        # unconditionally, so they are available even if widget_type was explicitly overridden
        # (e.g. widget_type='ui.radio' or 'checkbox_group') and _infer_widget_type is skipped below.
        if nv_field_info.literal_options is None:
            nv_field_info.literal_options = self._extract_literal_options(field_type)
            if nv_field_info.literal_options is not None:
                log.debug(f"_field_info_from_pydantic: {field_name=} Literal options: {nv_field_info.literal_options}")

        if nv_field_info.widget_type is None:
            self._infer_widget_type(field_name, field_type, nv_field_info)
        else:
            log.debug(f"_field_info_from_pydantic: {field_name=} widget_type already set: {nv_field_info.widget_type}")

        self._apply_pydantic_metadata(field_name, nv_field_info, py_field_info)

        log.debug(f"_field_info_from_pydantic: {field_name=} result: widget_type={nv_field_info.widget_type} label={nv_field_info.label!r} required={nv_field_info.required} min={nv_field_info.min} max={nv_field_info.max} step={nv_field_info.step}")
        return nv_field_info

    def from_sqlmodel(self, field_name: str, field_type: type) -> FieldInfo | None:
        import sqlalchemy  # sqlmodel is available (checked by caller)
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

    @staticmethod
    def _extract_literal_options(field_type: type) -> list | None:
        """Literal options for a Literal[...] field, or for a list[Literal[...]] field. Optional is unwrapped first."""
        if typing.get_origin(field_type) is typing.Union or isinstance(field_type, types.UnionType):
            non_none = [t for t in typing.get_args(field_type) if t is not type(None)]
            if len(non_none) == 1:
                field_type = non_none[0]

        if typing.get_origin(field_type) == typing.Literal:
            return list(typing.get_args(field_type))

        if typing.get_origin(field_type) == list:
            args = typing.get_args(field_type)
            if len(args) == 1 and typing.get_origin(args[0]) is typing.Literal:
                return list(typing.get_args(args[0]))

        return None

    def _infer_widget_type(self, field_name: str, field_type: type, nv_field_info: FieldInfo) -> None:
        if typing.get_origin(field_type) is typing.Union or isinstance(field_type, types.UnionType):
            union_types = [t for t in typing.get_args(field_type) if t is not type(None)]
            if len(union_types) == 1:
                field_type = union_types[0]
                log.debug(f"_field_info_from_pydantic: {field_name=} unwrapped Optional -> {field_type}")
            else:
                log.warning(f"Field '{field_name}' has a Union type with multiple non-None types, cannot determine widget type: {field_type=} {union_types=}")

        if field_type is pydantic.SecretStr:
            nv_field_info.widget_type = 'ui.input'
            for attr in ('password', 'password_toggle_button'):
                if attr not in vars(nv_field_info):  # not explicitly set by the user
                    setattr(nv_field_info, attr, True)
            log.debug(f"_field_info_from_pydantic: {field_name=} SecretStr -> password input")
        elif field_type in self._widget_lookup:
            nv_field_info.widget_type = self._widget_lookup[field_type]
            log.debug(f"_field_info_from_pydantic: {field_name=} widget_type from lookup: {nv_field_info.widget_type}")
        elif typing.get_origin(field_type) == typing.Literal:
            nv_field_info.widget_type = 'ui.select'
            if nv_field_info.options is None:
                nv_field_info.options = list(typing.get_args(field_type))
            log.debug(f"_field_info_from_pydantic: {field_name=} widget_type=ui.select options={nv_field_info.options}")
        elif isinstance(field_type, type) and issubclass(field_type, enum.Enum):
            nv_field_info.widget_type = 'ui.select'
            if nv_field_info.options is None:
                nv_field_info.options = {member: member.name for member in field_type}
            log.debug(f"_field_info_from_pydantic: {field_name=} widget_type=ui.select (Enum) options={nv_field_info.options}")
        elif typing.get_origin(field_type) == list:
            self._infer_list_widget_type(field_name, field_type, nv_field_info)
        else:
            nv_field_info.widget_type = 'ui.input'
            log.debug(f"_field_info_from_pydantic: {field_name=} unrecognised type {field_type}, defaulting widget_type=ui.input")

    def _infer_list_widget_type(self, field_name: str, field_type: type, nv_field_info: FieldInfo) -> None:
        args = typing.get_args(field_type)

        # list[Literal[...]] -> multi-select. The list item is a Literal, so the
        # allowed values become the select options and multiple is enabled.
        if len(args) == 1 and typing.get_origin(args[0]) is typing.Literal:
            literal_args = list(typing.get_args(args[0]))
            nv_field_info.widget_type = 'ui.select'
            nv_field_info.multiple = True
            if nv_field_info.literal_options is None:
                nv_field_info.literal_options = literal_args
            if nv_field_info.options is None:
                nv_field_info.options = literal_args
            log.debug(f"_field_info_from_pydantic: {field_name=} list[Literal] -> ui.select multiple options={literal_args}")
            return

        if nv_field_info.item_type is None:
            for arg in typing.get_args(field_type):
                # Unwrap Annotated[str, Field(pattern=..., min_length=..., ...)] to the
                # underlying type. The constraints themselves don't need any special
                # handling here: they stay part of the item's annotation and are enforced
                # by pydantic's own model_validate(), which Fields.validation_errors() calls.
                if typing.get_origin(arg) is typing.Annotated:
                    arg = typing.get_args(arg)[0]
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
        # One source, one destination: title -> label, description -> description,
        # examples[0] -> placeholder (an example of the expected input). Where the description
        # is *shown* is not decided here — it is a rendering choice (`description_as`), so the
        # resolver carries the text and stays out of it. hint and tooltip stay the author's.
        # An explicit label='' means "no label"; only an unset label auto-generates one from the
        # pydantic title or the field name. The sparse __dict__ tells the two apart — '' is
        # falsy, so `not label` would treat a deliberate empty label as unset.
        if 'label' not in vars(nv_field_info):
            nv_field_info.label = py_field_info.title or self._label_from_name(field_name)
        if nv_field_info.description is None:
            nv_field_info.description = py_field_info.description
        if nv_field_info.placeholder is None and py_field_info.examples:
            nv_field_info.placeholder = str(py_field_info.examples[0])
        if nv_field_info.required is None:
            nv_field_info.required = py_field_info.is_required()
        self._apply_frozen(field_name, nv_field_info, py_field_info)

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

    def _apply_frozen(self, field_name: str, nv_field_info: FieldInfo, py_field_info: pydantic.fields.FieldInfo) -> None:
        """
        A frozen field cannot be written: pydantic raises ValidationError on every assignment,
        including on the model_copy() a form edits. Rendering it enabled produces a write error
        on the first keystroke, so frozen implies editable=False.
        """
        frozen = bool(py_field_info.frozen) or bool(self._item_type.model_config.get('frozen'))
        if not frozen:
            return
        if 'editable' in vars(nv_field_info):  # explicitly set by the user — explicit wins
            if nv_field_info.editable:
                log.warning(
                    f"Field '{field_name}' is frozen in the model but was declared editable=True — "
                    f"writing to it will fail. Remove editable=True or the frozen=True."
                )
            return
        nv_field_info.editable = False

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


@dataclasses.dataclass(frozen=True, slots=True)
class LayoutField:
    """One field in a form layout, with the CSS classes given after its colon (if any)."""
    name: str
    classes: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class LayoutAction:
    """
    One action button in a form layout, written '@name' and looked up in the form's `actions`.
    An action is layout, not a field: it has no value, no validation and no place in the model.
    """
    name: str
    classes: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class LayoutGroup:
    """
    A container in a form layout: a row, a column, or — with a title — a section.
    Nesting alternates row and column; a titled group is always a column, so that a section
    reads the same wherever it sits.

    A section comes in two shapes, told apart by `card`: '# Title' draws a card around its
    fields, '## Title' only sets the heading above them. Both headings look the same.
    """
    children: tuple['LayoutField | LayoutAction | LayoutGroup', ...]
    row: bool = False
    title: str | None = None
    classes: str | None = None
    card: bool = False


def parse_layout(spec: typing.Any, valid_names: typing.Container[str], *, valid_actions: typing.Container[str] = (),
                 row: bool = False, path: str = 'layout') -> LayoutGroup:
    """
    Parse a nested field layout into LayoutGroups, LayoutFields and LayoutActions.

    A list holds field names; a nested list opens a container (rows and columns alternate).
    Leading strings are metadata for their own group — '# Title' makes it a titled card,
    '## Title' a section with the same heading but no card around it, ':classes' replaces the
    container's default CSS classes. A field name may carry classes of its own after a colon:
    'street:sm:w-2/3' (only the first colon separates, so Tailwind prefixes stay intact).

    '@name' is an action button rather than a field, and must be declared in `valid_actions` —
    the form's `actions` table, which holds the callback the name cannot carry.

    Raises ValueError with the position of the offending element.
    """
    if not isinstance(spec, (list, tuple)):
        raise ValueError(f"{path}: expected a list of field names, got {type(spec).__name__}")

    title: str | None = None
    card = False
    classes: str | None = None
    first_field = 0
    for index, element in enumerate(spec):
        if not (isinstance(element, str) and element[:1] in ('#', ':')):
            break
        where = f'{path}[{index}]'
        if element.startswith('#'):
            if title is not None:
                raise ValueError(f"{where}: the group already has a title ('{title}')")
            level = len(element) - len(element.lstrip('#'))
            if level > 2:
                raise ValueError(f"{where}: '{'#' * level}' is not a heading level — "
                                 f"'#' draws a card, '##' only the heading")
            card = level == 1
            title = element.lstrip('#').strip()
            if not title:
                raise ValueError(f"{where}: '{'#' * level}' needs a title")
        else:
            if classes is not None:
                raise ValueError(f"{where}: the group already has classes ('{classes}')")
            classes = element[1:].strip()
            if not classes:
                raise ValueError(f"{where}: ':' needs at least one CSS class")
        first_field = index + 1

    row = False if title is not None else row  # a section stacks: its heading sits above it

    children: list[LayoutField | LayoutAction | LayoutGroup] = []
    for index, element in enumerate(spec[first_field:], start=first_field):
        where = f'{path}[{index}]'
        if isinstance(element, str):
            if element[:1] in ('#', ':'):
                raise ValueError(f"{where}: '{element}' is group metadata and must come before the fields")
            name, _, hint = element.partition(':')
            name, hint = name.strip(), hint.strip()
            if name.startswith('@'):
                action = name[1:]
                if not action:
                    raise ValueError(f"{where}: '@' needs an action name")
                if action not in valid_actions:
                    raise ValueError(f"{where}: unknown action '{action}' — every '@name' needs an "
                                     f"entry in the form's actions")
                children.append(LayoutAction(action, hint or None))
            elif name not in valid_names:
                raise ValueError(f"{where}: unknown field '{name}'")
            else:
                children.append(LayoutField(name, hint or None))
        elif isinstance(element, (list, tuple)):
            children.append(parse_layout(element, valid_names, valid_actions=valid_actions, row=not row, path=where))
        else:
            raise ValueError(f"{where}: expected a field name or a nested list, got {type(element).__name__}")

    if not children:
        raise ValueError(f"{path}: a layout group must contain at least one field")
    return LayoutGroup(tuple(children), row=row, title=title, classes=classes, card=card)


def layout_field_names(group: LayoutGroup) -> list[str]:
    """All field names in a layout, in rendering order. Actions are not fields and not listed."""
    names: list[str] = []
    for child in group.children:
        if isinstance(child, LayoutField):
            names.append(child.name)
        elif isinstance(child, LayoutGroup):
            names.extend(layout_field_names(child))
    return names


def layout_action_names(group: LayoutGroup) -> list[str]:
    """All action names in a layout, in rendering order."""
    names: list[str] = []
    for child in group.children:
        if isinstance(child, LayoutAction):
            names.append(child.name)
        elif isinstance(child, LayoutGroup):
            names.extend(layout_action_names(child))
    return names


class Fields(typing.Mapping[str, FieldInfo]):
    """
    Fields and field information for datamodel based UI components.
    """
    _item_type: type[pydantic.BaseModel]
    _include: list[str]
    _exclude: list[str]
    _field_names: list[str]
    _field_infos: dict[str, FieldInfo]
    _layout: LayoutGroup

    def __init__(self, item_type: type[pydantic.BaseModel], include: str | typing.Iterable[str] = '__all__', exclude: str | typing.Iterable[str] = '', field_infos: dict[str, FieldInfo] = {}, profile: str | None = None, layout: typing.Any = None, actions: typing.Container[str] = ()):
        self._item_type = item_type
        meta = getattr(item_type, 'Meta', None)

        if profile is not None:
            profiles: dict = getattr(meta, 'profiles', {}) if meta else {}
            if profile not in profiles:
                available = list(profiles.keys())
                raise ValueError(f"Profile '{profile}' not found in {item_type.__name__}.Meta.profiles. Available: {available}")
            include = profiles[profile]
        if layout is not None:
            include = layout  # an explicit layout is an inline profile: it defines the field set

        all_fields = set(item_type.model_fields.keys())

        # An explicit field list is parsed as a layout: a flat list is a layout without rows, so
        # there is one code path, one place that validates names — and one ordering rule, no
        # matter whether the fields were given as a list or as a comma-separated string.
        if isinstance(include, str) and include.strip() not in ('', '__all__'):
            include = [name.strip() for name in include.split(',') if name.strip()]
        parsed_layout: LayoutGroup | None = None
        if isinstance(include, (list, tuple)) and list(include) != ['__all__']:
            parsed_layout = parse_layout(include, all_fields, valid_actions=actions)
            include = layout_field_names(parsed_layout)
            duplicates = sorted({n for n in include if include.count(n) > 1})
            if duplicates:
                raise ValueError(f"Layout for '{item_type.__name__}' names field(s) more than once: {duplicates}")

        self._include = self._parse_field_names(include, all_fields, allow_all=True, model_name=item_type.__name__)
        self._exclude = self._parse_field_names(exclude, all_fields, allow_all=False, model_name=item_type.__name__)

        resolver = _FieldInfoResolver(item_type)
        self._field_names, self._field_infos = self._build_field_infos(resolver, meta, field_infos)
        if parsed_layout is None:
            self._apply_field_order(meta)
            self._layout = LayoutGroup(tuple(LayoutField(name) for name in self._field_names))
        else:
            # The layout defines the order; Meta.field_order does not apply on top of it.
            unavailable = [n for n in layout_field_names(parsed_layout) if n not in self._field_infos]
            if unavailable:
                raise ValueError(
                    f"Layout for '{item_type.__name__}' names field(s) that are not available: {unavailable} "
                    f"(excluded, private, or without usable type information)"
                )
            self._layout = parsed_layout
            self._field_names = layout_field_names(parsed_layout)

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
        is_sqlmodel = _SQLMODEL_AVAILABLE and issubclass(self._item_type, _SQLModel)
        # 'field_infos' is the documented name; 'field_info' (singular) is accepted for backward compatibility.
        meta_field_info: dict[str, FieldInfo] = {}
        if meta is not None:
            meta_field_info = getattr(meta, 'field_infos', None) or getattr(meta, 'field_info', {})

        names: list[str] = []
        infos: dict[str, FieldInfo] = {}

        # Collect annotations across the MRO so inherited model fields are included
        # (cls.__annotations__ only contains the class's own annotations). Base-class
        # fields come first, matching pydantic's model_fields ordering; an override
        # in a subclass keeps the base-class position (dict.update semantics).
        annotations: dict[str, typing.Any] = {}
        for klass in reversed(self._item_type.__mro__):
            annotations.update(getattr(klass, '__annotations__', {}))

        for field_name, field_type in annotations.items():
            if not self.is_included(field_name):
                continue

            fi: FieldInfo | None
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

    @property
    def layout(self) -> LayoutGroup:
        """
        The form layout: a tree of rows, columns and sections over the fields. Without an explicit
        layout this is a flat group in field order, which renders exactly as before.
        Grids and lists ignore the tree and read the flattened `field_names`.
        """
        return self._layout

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
