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


class TestMetaClass:
    def test_meta_sets_hidden(self):
        fields = Fields(MetaModel)
        assert fields['secret'].hidden is True

    def test_meta_does_not_affect_other_fields(self):
        fields = Fields(MetaModel)
        assert fields['name'].hidden is False


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
