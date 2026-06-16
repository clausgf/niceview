import datetime

import pydantic
import pytest

from niceview.dataadapter import ListModelAdapter
from niceview.modelform import ModelForm


class User(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=10, title='Name')
    age: int = pydantic.Field(default=0, ge=0, le=120)
    active: bool = True


class CrossFieldModel(pydantic.BaseModel):
    start: int = 0
    end: int = 10

    @pydantic.model_validator(mode='after')
    def check_start_before_end(self) -> 'CrossFieldModel':
        if self.start >= self.end:
            raise ValueError('start must be less than end')
        return self


class SimpleModel(pydantic.BaseModel):
    value: str = ''


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestModelFormInit:
    def test_init_with_valid_model(self):
        form = ModelForm(User)
        assert form._item_type is User

    def test_init_with_non_model_raises(self):
        with pytest.raises(TypeError):
            ModelForm(str)  # type: ignore

    def test_init_with_instance_raises(self):
        with pytest.raises(TypeError):
            ModelForm(User())  # type: ignore

    def test_defaults(self):
        form = ModelForm(User)
        assert form.title == ''
        assert form.autosave is False
        assert form.save_button is None
        assert form.refresh_button is None

    def test_title_kwarg(self):
        form = ModelForm(User, title='My Form')
        assert form.title == 'My Form'

    def test_autosave_kwarg(self):
        form = ModelForm(User, autosave=True)
        assert form.autosave is True

    def test_local_tz_default_is_none(self):
        assert ModelForm(User).local_tz is None

    def test_local_tz_kwarg(self):
        form = ModelForm(User, local_tz='Europe/Berlin')
        assert form.local_tz == 'Europe/Berlin'

    def test_unknown_kwarg_raises(self):
        with pytest.raises(TypeError):
            ModelForm(User, nonexistent_option=True)  # type: ignore

    def test_include_filters_fields(self):
        form = ModelForm(User, include=['name'])
        assert 'name' in form._fields
        assert 'age' not in form._fields

    def test_exclude_removes_fields(self):
        form = ModelForm(User, exclude=['active'])
        assert 'active' not in form._fields
        assert 'name' in form._fields


# ---------------------------------------------------------------------------
# from_item
# ---------------------------------------------------------------------------

class TestFromItem:
    def test_from_item_sets_validated_item(self):
        user = User(name='Alice', age=30)
        form = ModelForm.from_item(user)
        assert form.item is user

    def test_from_item_non_model_raises(self):
        with pytest.raises(TypeError):
            ModelForm.from_item('not a model')  # type: ignore

    def test_from_item_with_kwargs(self):
        user = User()
        form = ModelForm.from_item(user, title='Edit User')
        assert form.title == 'Edit User'

    def test_item_property_raises_when_not_set(self):
        form = ModelForm(User)
        with pytest.raises(ValueError):
            _ = form.item

    def test_item_setter_wrong_type_raises(self):
        form = ModelForm(User)
        with pytest.raises(TypeError):
            form.item = 'not a model'  # type: ignore


# ---------------------------------------------------------------------------
# set_item_from_model
# ---------------------------------------------------------------------------

class TestSetItemFromModel:
    def test_set_item_from_list_adapter(self):
        items = [User(name='Bob', age=25)]
        adapter = ListModelAdapter(User, items)
        form = ModelForm(User)
        form.set_item_from_model(adapter, 0)
        assert form.item.name == 'Bob'

    def test_set_item_returns_self(self):
        items = [User()]
        adapter = ListModelAdapter(User, items)
        form = ModelForm(User)
        result = form.set_item_from_model(adapter, 0)
        assert result is form


class TestRefresh:
    def test_refresh_without_model_raises(self):
        form = ModelForm(User)
        with pytest.raises(ValueError):
            form._refresh()

    def test_refresh_updates_validated_item(self):
        items = [User(name='Bob', age=25)]
        adapter = ListModelAdapter(User, items)
        form = ModelForm(User)
        form.set_item_from_model(adapter, 0)
        items[0] = User(name='Alice', age=30)
        adapter.update(items[0], '0')
        form._refresh()
        assert form.item.name == 'Alice'
        assert form.item.age == 30


class TestAutosaveWithoutAdapter:
    def test_autosave_does_not_crash_without_adapter(self):
        user = User(name='Alice', age=30)
        form = ModelForm.from_item(user, autosave=True)
        # Simulating what _handle_value_change does after a field change
        form._current_item = User.model_construct(name='Bob', age=30)
        # Must not raise even though no adapter is set
        form._handle_value_change('name', type('E', (), {'sender': None, 'client': None})())

    def test_item_setter_updates_current_item(self):
        user1 = User(name='Alice', age=30)
        user2 = User(name='Bob', age=25)
        form = ModelForm.from_item(user1)
        form.item = user2
        assert form._current_item.name == 'Bob'
        assert form._current_item.age == 25


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_valid_item_no_errors(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        assert form.has_validation_errors() is False

    def test_invalid_current_item_sets_errors(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        form._current_item = User.model_construct(name='X' * 20, age=30)
        form._validate()
        assert form.has_validation_errors() is True

    def test_invalid_age_sets_error(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        form._current_item = User.model_construct(name='Alice', age=999)
        form._validate()
        assert 'age' in form._validation_error_messages

    def test_error_message_is_string(self):
        form = ModelForm.from_item(User())
        form._current_item = User.model_construct(name='X' * 20, age=0)
        form._validate()
        assert isinstance(form._validation_error_messages.get('name'), str)

    def test_nonfield_errors_stored_for_cross_field_validation(self):
        form = ModelForm.from_item(CrossFieldModel(start=0, end=10))
        form._current_item = CrossFieldModel.model_construct(start=10, end=5)
        form._validate()
        assert form._nonfield_validation_errors != []

    def test_nonfield_errors_empty_when_valid(self):
        form = ModelForm.from_item(CrossFieldModel(start=0, end=10))
        assert form._nonfield_validation_errors == []

    def test_has_validation_errors_includes_nonfield_errors(self):
        form = ModelForm.from_item(CrossFieldModel(start=0, end=10))
        form._current_item = CrossFieldModel.model_construct(start=10, end=5)
        form._validate()
        assert form.has_validation_errors() is True

    def test_nonfield_error_element_initially_none(self):
        form = ModelForm(User)
        assert form._nonfield_error_element is None


# ---------------------------------------------------------------------------
# on_change
# ---------------------------------------------------------------------------

class TestOnChange:
    def test_on_change_registers_callback(self):
        form = ModelForm(User)
        cb = lambda e: None
        form.on_change(cb)
        assert cb in form._change_handlers

    def test_on_change_non_callable_raises(self):
        form = ModelForm(User)
        with pytest.raises(TypeError):
            form.on_change('not callable')  # type: ignore

    def test_on_change_returns_self(self):
        form = ModelForm(User)
        result = form.on_change(lambda e: None)
        assert result is form

    def test_multiple_callbacks_registered(self):
        form = ModelForm(User)
        cb1 = lambda e: None
        cb2 = lambda e: None
        form.on_change(cb1)
        form.on_change(cb2)
        assert cb1 in form._change_handlers
        assert cb2 in form._change_handlers

    def test_on_change_via_init_kwarg(self):
        cb = lambda e: None
        form = ModelForm(User, on_change=cb)
        assert cb in form._change_handlers
