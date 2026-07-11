import datetime
from typing import Annotated, Literal

import pydantic
import pytest

import niceview
from niceview.fieldinfo import FieldInfo
from niceview.fields import Fields


# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------

class SimpleModel(pydantic.BaseModel):
    name: str = ''
    age: int = 0
    score: float = 0.0
    active: bool = True
    birthday: datetime.date = datetime.date(2000, 1, 1)
    meeting_time: datetime.time = datetime.time(9, 0)
    created_at: datetime.datetime = datetime.datetime(2000, 1, 1)
    duration: datetime.timedelta = datetime.timedelta(days=1)


class LiteralModel(pydantic.BaseModel):
    color: Literal['red', 'green', 'blue'] = 'red'
    nullable: Literal['Yes', 'No', None] = None


class SubItem(pydantic.BaseModel):
    value: str = ''

class ListModel(pydantic.BaseModel):
    tags: list[str] = []
    items: list[SubItem] = []


class MultiSelectModel(pydantic.BaseModel):
    perms: list[Literal['read', 'write', 'admin']] = []
    opt_perms: list[Literal['read', 'write', 'admin']] | None = None


class CheckboxGroupModel(pydantic.BaseModel):
    perms: Annotated[list[Literal['read', 'write', 'admin']], niceview.Field(widget_type='checkbox_group')] = []
    opt_perms: Annotated[list[Literal['read', 'write', 'admin']] | None, niceview.Field(widget_type='checkbox_group')] = None
    perms_inline: Annotated[list[Literal['read', 'write', 'admin']], niceview.Field(widget_type='checkbox_group', props='inline')] = []


class ConstrainedListModel(pydantic.BaseModel):
    tags: list[Annotated[str, pydantic.Field(pattern=r'^[a-z]+$', min_length=2, max_length=10)]] = []
    scores: list[Annotated[int, pydantic.Field(ge=0, le=100)]] = []


class ConstrainedListAndItemsModel(pydantic.BaseModel):
    # constraints on both the list itself (min/max_length) and its items (pattern, min/max_length)
    tags: Annotated[
        list[Annotated[str, pydantic.Field(pattern=r'^[a-z]+$', min_length=2, max_length=10)]],
        pydantic.Field(min_length=1, max_length=3),
    ] = []


class TitledModel(pydantic.BaseModel):
    first_name: str = pydantic.Field(default='', title='First Name', description='Your first name')
    age: int = pydantic.Field(default=0, ge=0, le=150)


class AnnotatedModel(pydantic.BaseModel):
    weight: Annotated[
        float,
        pydantic.Field(default=50.0),
        niceview.Field(min=10.0, max=200.0, label='Weight (kg)'),
    ]


class MetaModel(pydantic.BaseModel):
    name: str = ''
    secret: str = ''

    class Meta:
        field_info = {
            'secret': FieldInfo(hidden=True),
        }


class ValidatedModel(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=5, title='Name')
    age: int = pydantic.Field(default=0, ge=0, le=120)


# ---------------------------------------------------------------------------
# Widget type inference
# ---------------------------------------------------------------------------

class TestWidgetTypeInference:
    def setup_method(self):
        self.fields = Fields(SimpleModel)

    def test_str_to_input(self):
        assert self.fields['name'].widget_type == 'ui.input'

    def test_int_to_number(self):
        assert self.fields['age'].widget_type == 'ui.number'

    def test_float_to_number(self):
        assert self.fields['score'].widget_type == 'ui.number'

    def test_bool_to_switch(self):
        assert self.fields['active'].widget_type == 'ui.switch'

    def test_date_to_date(self):
        assert self.fields['birthday'].widget_type == 'date'

    def test_time_to_time(self):
        assert self.fields['meeting_time'].widget_type == 'time'

    def test_datetime_to_datetime(self):
        assert self.fields['created_at'].widget_type == 'datetime'

    def test_timedelta_to_timedelta(self):
        assert self.fields['duration'].widget_type == 'timedelta'

    def test_literal_to_select(self):
        fields = Fields(LiteralModel)
        assert fields['color'].widget_type == 'ui.select'

    def test_literal_select_options(self):
        fields = Fields(LiteralModel)
        assert fields['color'].select_options == ['red', 'green', 'blue']

    def test_list_str_to_input_chips(self):
        fields = Fields(ListModel)
        assert fields['tags'].widget_type == 'ui.input_chips'

    def test_list_basemodel_to_editgrid(self):
        fields = Fields(ListModel)
        assert fields['items'].widget_type == 'editgrid'

    def test_list_basemodel_item_type(self):
        fields = Fields(ListModel)
        assert fields['items'].item_type is SubItem

    def test_list_literal_to_select(self):
        fields = Fields(MultiSelectModel)
        assert fields['perms'].widget_type == 'ui.select'

    def test_list_literal_multiple(self):
        fields = Fields(MultiSelectModel)
        assert fields['perms'].multiple is True

    def test_list_literal_options(self):
        fields = Fields(MultiSelectModel)
        assert fields['perms'].select_options == ['read', 'write', 'admin']

    def test_list_annotated_str_to_input_chips(self):
        fields = Fields(ConstrainedListModel)
        assert fields['tags'].widget_type == 'ui.input_chips'
        assert fields['tags'].item_type is str

    def test_list_annotated_int_item_type(self):
        fields = Fields(ConstrainedListModel)
        assert fields['scores'].item_type is int

    def test_list_literal_checkbox_group_widget_type_preserved(self):
        # widget_type='checkbox_group' is an explicit override; must not be clobbered
        # by list[Literal] auto-inference (which would otherwise pick 'ui.select').
        fields = Fields(CheckboxGroupModel)
        assert fields['perms'].widget_type == 'checkbox_group'

    def test_list_literal_checkbox_group_literal_options_populated(self):
        # literal_options must be extracted even though widget_type was pre-set, so
        # _infer_list_widget_type (which normally does this) never runs.
        fields = Fields(CheckboxGroupModel)
        assert fields['perms'].literal_options == ['read', 'write', 'admin']

    def test_optional_list_literal_checkbox_group_literal_options_populated(self):
        fields = Fields(CheckboxGroupModel)
        assert fields['opt_perms'].literal_options == ['read', 'write', 'admin']

    def test_checkbox_group_inline_prop_preserved(self):
        fields = Fields(CheckboxGroupModel)
        assert fields['perms_inline'].props == 'inline'

    def test_optional_list_literal_to_select(self):
        fields = Fields(MultiSelectModel)
        assert fields['opt_perms'].widget_type == 'ui.select'

    def test_optional_list_literal_multiple(self):
        fields = Fields(MultiSelectModel)
        assert fields['opt_perms'].multiple is True

    def test_optional_list_literal_options(self):
        fields = Fields(MultiSelectModel)
        assert fields['opt_perms'].select_options == ['read', 'write', 'admin']


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

class TestLabels:
    def test_label_from_field_name(self):
        fields = Fields(SimpleModel)
        assert fields['name'].label == 'Name'

    def test_label_snake_case_to_capitalized(self):
        class M(pydantic.BaseModel):
            first_name: str = ''
        fields = Fields(M)
        assert fields['first_name'].label == 'First name'

    def test_label_from_pydantic_title(self):
        fields = Fields(TitledModel)
        assert fields['first_name'].label == 'First Name'

    def test_label_from_niceview_field_annotation(self):
        fields = Fields(AnnotatedModel)
        assert fields['weight'].label == 'Weight (kg)'

    def test_placeholder_from_pydantic_description(self):
        fields = Fields(TitledModel)
        assert fields['first_name'].placeholder == 'Your first name'


# ---------------------------------------------------------------------------
# Include / Exclude
# ---------------------------------------------------------------------------

class TestIncludeExclude:
    def test_include_all_by_default(self):
        fields = Fields(SimpleModel)
        assert set(fields.field_names) == set(SimpleModel.model_fields.keys())

    def test_include_subset(self):
        fields = Fields(SimpleModel, include=['name', 'age'])
        assert list(fields.field_names) == ['name', 'age']

    def test_include_excludes_others(self):
        fields = Fields(SimpleModel, include=['name'])
        assert 'score' not in fields

    def test_exclude_removes_fields(self):
        fields = Fields(SimpleModel, exclude=['score', 'active'])
        assert 'score' not in fields
        assert 'active' not in fields
        assert 'name' in fields

    def test_exclude_as_string(self):
        fields = Fields(SimpleModel, exclude='score, active')
        assert 'score' not in fields
        assert 'name' in fields

    def test_include_as_string(self):
        fields = Fields(SimpleModel, include='name, age')
        assert list(fields.field_names) == ['name', 'age']

    def test_invalid_include_raises(self):
        with pytest.raises(ValueError):
            Fields(SimpleModel, include=['nonexistent'])

    def test_invalid_exclude_raises(self):
        with pytest.raises(ValueError):
            Fields(SimpleModel, exclude=['nonexistent'])


# ---------------------------------------------------------------------------
# niceview.Field annotation & Meta class
# ---------------------------------------------------------------------------

class TestNiceviewFieldAnnotation:
    def test_min_from_annotation(self):
        fields = Fields(AnnotatedModel)
        assert fields['weight'].min == 10.0

    def test_max_from_annotation(self):
        fields = Fields(AnnotatedModel)
        assert fields['weight'].max == 200.0


class TestPydanticConstraints:
    def test_ge_sets_min(self):
        fields = Fields(TitledModel)
        assert fields['age'].min == 0.0

    def test_le_sets_max(self):
        fields = Fields(TitledModel)
        assert fields['age'].max == 150.0

    def test_constraints_do_not_override_niceview_field(self):
        class M(pydantic.BaseModel):
            x: Annotated[int, pydantic.Field(default=0, ge=5), niceview.Field(min=1.0)]
        fields = Fields(M)
        assert fields['x'].min == 1.0  # niceview.Field takes priority

    def test_gt_sets_min(self):
        class M(pydantic.BaseModel):
            x: int = pydantic.Field(default=1, gt=0)
        fields = Fields(M)
        assert fields['x'].min == 0.0

    def test_lt_sets_max(self):
        class M(pydantic.BaseModel):
            x: int = pydantic.Field(default=0, lt=100)
        fields = Fields(M)
        assert fields['x'].max == 100.0


class TestFieldInfosKwarg:
    def test_field_infos_overrides_label(self):
        fields = Fields(SimpleModel, field_infos={'name': FieldInfo(label='Full Name')})
        assert fields['name'].label == 'Full Name'

    def test_field_infos_overrides_hidden(self):
        fields = Fields(SimpleModel, field_infos={'age': FieldInfo(hidden=True)})
        assert fields['age'].hidden is True

    def test_field_infos_does_not_affect_other_fields(self):
        fields = Fields(SimpleModel, field_infos={'name': FieldInfo(hidden=True)})
        assert fields['age'].hidden is False

    def test_field_infos_merges_with_meta(self):
        # field_infos kwarg takes priority over Meta class
        fields = Fields(MetaModel, field_infos={'secret': FieldInfo(label='Override')})
        assert fields['secret'].label == 'Override'
        assert fields['secret'].hidden is True  # from Meta class, preserved


class TestMetaClass:
    def test_meta_sets_hidden(self):
        fields = Fields(MetaModel)
        assert fields['secret'].hidden is True

    def test_meta_does_not_affect_other_fields(self):
        fields = Fields(MetaModel)
        assert fields['name'].hidden is False


# ---------------------------------------------------------------------------
# Meta.field_order
# ---------------------------------------------------------------------------

class OrderedModel(pydantic.BaseModel):
    a: str = ''
    b: str = ''
    c: str = ''

    class Meta:
        field_order = ['c', 'a', 'b']


class PartialOrderModel(pydantic.BaseModel):
    a: str = ''
    b: str = ''
    c: str = ''

    class Meta:
        field_order = ['c', 'a']


class TestMetaFieldOrder:
    def test_full_reorder(self):
        fields = Fields(OrderedModel)
        assert list(fields) == ['c', 'a', 'b']

    def test_partial_order_remaining_appended(self):
        fields = Fields(PartialOrderModel)
        assert list(fields) == ['c', 'a', 'b']

    def test_unknown_field_raises(self):
        class BadOrderModel(pydantic.BaseModel):
            x: str = ''
            class Meta:
                field_order = ['x', 'nonexistent']
        with pytest.raises(ValueError, match='nonexistent'):
            Fields(BadOrderModel)

    def test_no_field_order_preserves_declaration_order(self):
        fields = Fields(SimpleModel, include=['name', 'age'])
        assert list(fields) == ['name', 'age']


# ---------------------------------------------------------------------------
# Optional / Union unwrapping
# ---------------------------------------------------------------------------

class OptionalModel(pydantic.BaseModel):
    value: int | None = None
    name: str | None = None


class TestOptionalUnwrapping:
    def test_optional_int_gets_number_widget(self):
        fields = Fields(OptionalModel)
        assert fields['value'].widget_type == 'ui.number'

    def test_optional_str_gets_input_widget(self):
        fields = Fields(OptionalModel)
        assert fields['name'].widget_type == 'ui.input'


# ---------------------------------------------------------------------------
# Merge preserves framework-internal attributes (field_type, literal_options)
# ---------------------------------------------------------------------------

class LiteralMetaModel(pydantic.BaseModel):
    color: Literal['red', 'green', 'blue'] = 'red'

    class Meta:
        field_info = {
            'color': FieldInfo(widget_type='ui.radio'),
        }


class TestMergePreservesInternalAttrs:
    def test_literal_options_preserved_after_meta_override(self):
        # Regression: _merge_field_infos used to lose literal_options because it is
        # not in _FIELD_INFO_KWARGS and was not copied from the base FieldInfo.
        fields = Fields(LiteralMetaModel)
        assert fields['color'].literal_options == ['red', 'green', 'blue']

    def test_literal_options_preserved_after_field_infos_kwarg(self):
        fields = Fields(LiteralModel, field_infos={'color': FieldInfo(widget_type='ui.radio')})
        assert fields['color'].literal_options == ['red', 'green', 'blue']

    def test_field_type_preserved_after_meta_override(self):
        fields = Fields(MetaModel, field_infos={'name': FieldInfo(label='Full Name')})
        assert fields['name'].field_type == str

    def test_field_type_preserved_after_field_infos_kwarg(self):
        # field_type is also framework-internal and was lost in the same bug
        fields = Fields(SimpleModel, field_infos={'age': FieldInfo(label='Age')})
        assert fields['age'].field_type == int


# ---------------------------------------------------------------------------
# Mapping protocol
# ---------------------------------------------------------------------------

class TestMappingProtocol:
    def test_len(self):
        fields = Fields(SimpleModel)
        assert len(fields) == len(SimpleModel.model_fields)

    def test_iter_yields_field_names(self):
        fields = Fields(SimpleModel, include=['name', 'age'])
        assert list(fields) == ['name', 'age']

    def test_getitem(self):
        fields = Fields(SimpleModel)
        fi = fields['name']
        assert isinstance(fi, FieldInfo)

    def test_getitem_missing_raises(self):
        fields = Fields(SimpleModel)
        with pytest.raises(KeyError):
            _ = fields['nonexistent']


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_data_no_errors(self):
        fields = Fields(ValidatedModel)
        field_errors, nonfield_errors = fields.validation_errors({'name': 'Hi', 'age': 30})
        assert field_errors == {}
        assert nonfield_errors == []

    def test_name_too_long_returns_field_error(self):
        fields = Fields(ValidatedModel)
        field_errors, _ = fields.validation_errors({'name': 'TooLongName', 'age': 30})
        assert 'name' in field_errors

    def test_age_out_of_range_returns_field_error(self):
        fields = Fields(ValidatedModel)
        field_errors, _ = fields.validation_errors({'name': 'Hi', 'age': 200})
        assert 'age' in field_errors

    def test_validation_error_list_uses_label(self):
        fields = Fields(ValidatedModel)
        errors = fields.validation_error_list({'name': 'TooLongName', 'age': 30})
        assert any('Name' in e for e in errors)

    def test_validation_error_list_empty_when_valid(self):
        fields = Fields(ValidatedModel)
        assert fields.validation_error_list({'name': 'Hi', 'age': 30}) == []


# ---------------------------------------------------------------------------
# Constrained list items: list[Annotated[str/int, Field(...)]]
# ---------------------------------------------------------------------------

class TestConstrainedListValidation:
    def test_valid_items_no_errors(self):
        fields = Fields(ConstrainedListModel)
        field_errors, _ = fields.validation_errors({'tags': ['ok', 'go'], 'scores': [0, 50, 100]})
        assert field_errors == {}

    def test_pattern_violation_returns_field_error(self):
        fields = Fields(ConstrainedListModel)
        field_errors, _ = fields.validation_errors({'tags': ['ok', 'BAD1'], 'scores': []})
        assert 'tags' in field_errors

    def test_min_length_violation_returns_field_error(self):
        fields = Fields(ConstrainedListModel)
        field_errors, _ = fields.validation_errors({'tags': ['a'], 'scores': []})
        assert 'tags' in field_errors

    def test_max_length_violation_returns_field_error(self):
        fields = Fields(ConstrainedListModel)
        field_errors, _ = fields.validation_errors({'tags': ['waytoolongvalue'], 'scores': []})
        assert 'tags' in field_errors

    def test_numeric_range_violation_returns_field_error(self):
        fields = Fields(ConstrainedListModel)
        field_errors, _ = fields.validation_errors({'tags': [], 'scores': [200]})
        assert 'scores' in field_errors


# ---------------------------------------------------------------------------
# Regression: constraints on the list itself (Annotated[list[...], Field(...)])
# combine correctly with constraints on its items (list[Annotated[...]])
# ---------------------------------------------------------------------------

class TestConstrainedListAndItemsValidation:
    def test_widget_type_still_input_chips(self):
        fields = Fields(ConstrainedListAndItemsModel)
        assert fields['tags'].widget_type == 'ui.input_chips'
        assert fields['tags'].item_type is str

    def test_valid_no_errors(self):
        fields = Fields(ConstrainedListAndItemsModel)
        field_errors, _ = fields.validation_errors({'tags': ['ab', 'cd']})
        assert field_errors == {}

    def test_too_few_items_violates_list_min_length(self):
        fields = Fields(ConstrainedListAndItemsModel)
        field_errors, _ = fields.validation_errors({'tags': []})
        assert 'tags' in field_errors

    def test_too_many_items_violates_list_max_length(self):
        fields = Fields(ConstrainedListAndItemsModel)
        field_errors, _ = fields.validation_errors({'tags': ['ab', 'cd', 'ef', 'gh']})
        assert 'tags' in field_errors

    def test_item_pattern_violation_within_valid_list_length(self):
        fields = Fields(ConstrainedListAndItemsModel)
        field_errors, _ = fields.validation_errors({'tags': ['ok', 'BAD1']})
        assert 'tags' in field_errors

    def test_multiple_item_errors_are_combined_on_same_field(self):
        fields = Fields(ConstrainedListAndItemsModel)
        field_errors, _ = fields.validation_errors({'tags': ['BAD1', 'x']})
        assert 'tags' in field_errors
        # both the pattern violation (BAD1) and the min_length violation (x) are reported
        assert 'pattern' in field_errors['tags']
        assert 'at least 2 characters' in field_errors['tags']


# ---------------------------------------------------------------------------
# Inherited fields (regression: cls.__annotations__ misses base-class fields)
# ---------------------------------------------------------------------------

class _BasePerson(pydantic.BaseModel):
    name: str = ''


class _Employee(_BasePerson):
    salary: int = 0


class TestInheritedFields:
    def test_inherited_field_included(self):
        fields = Fields(_Employee)
        assert 'name' in fields
        assert 'salary' in fields

    def test_base_fields_come_first(self):
        fields = Fields(_Employee)
        assert list(fields) == ['name', 'salary']

    def test_overridden_field_keeps_base_position(self):
        class _Manager(_Employee):
            name: str = 'boss'  # override
        fields = Fields(_Manager)
        assert list(fields) == ['name', 'salary']


# ---------------------------------------------------------------------------
# Annotated FieldInfo must not be mutated (it is shared class-level state)
# ---------------------------------------------------------------------------

class TestAnnotatedFieldInfoNotMutated:
    def test_metadata_instance_unchanged_after_resolution(self):
        nv = niceview.Field(min=5)

        class M(pydantic.BaseModel):
            x: Annotated[int, pydantic.Field(default=0), nv] = 0

        before = dict(vars(nv))
        fields = Fields(M)
        assert vars(nv) == before  # no widget_type/label/etc. leaked into the annotation
        assert fields['x'] is not nv  # resolution works on a copy
        assert fields['x'].min == 5  # values still transferred
        assert fields['x'].widget_type == 'ui.number'


# ---------------------------------------------------------------------------
# required resolution from pydantic
# ---------------------------------------------------------------------------

class TestRequiredResolution:
    def test_required_field_resolved_true(self):
        class M(pydantic.BaseModel):
            req: str

        assert Fields(M)['req'].required is True

    def test_optional_field_resolved_false(self):
        class M(pydantic.BaseModel):
            opt: str = 'x'

        assert Fields(M)['opt'].required is False

    def test_explicit_required_not_overwritten(self):
        class M(pydantic.BaseModel):
            opt: Annotated[str, niceview.Field(required=True)] = 'x'

        assert Fields(M)['opt'].required is True


# ---------------------------------------------------------------------------
# Meta.field_infos (documented plural name) and Meta.field_info (legacy)
# ---------------------------------------------------------------------------

class TestMetaFieldInfosNames:
    def test_plural_field_infos_applied(self):
        class M(pydantic.BaseModel):
            name: str = ''
            secret: str = ''

            class Meta:
                field_infos = {'secret': FieldInfo(hidden=True)}

        assert Fields(M)['secret'].hidden is True

    def test_singular_field_info_still_works(self):
        class M(pydantic.BaseModel):
            name: str = ''
            secret: str = ''

            class Meta:
                field_info = {'secret': FieldInfo(hidden=True)}

        assert Fields(M)['secret'].hidden is True
