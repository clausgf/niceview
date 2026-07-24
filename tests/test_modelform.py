import datetime
import json
import typing
from unittest.mock import MagicMock

import pydantic
import pytest
from nicegui import ui

import sqlmodel

from niceview.dataadapter import BoundItem, ListAdapter, JsonAdapter, SqlModelAdapter
from niceview.modelform import ModelForm


@pytest.fixture(autouse=True)
def mock_ui_notify(monkeypatch):
    """Suppress ui.notify() calls in unit tests that invoke _save()/_refresh()
    directly outside a NiceGUI client context."""
    monkeypatch.setattr(ui, 'notify', MagicMock())


class Tag(pydantic.BaseModel):
    label: str = ''

    def __str__(self):
        return self.label


class User(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=10, title='Name')
    age: int = pydantic.Field(default=0, ge=0, le=120)
    active: bool = True
    tags: list[Tag] = pydantic.Field(default_factory=list)


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


class NumberModel(pydantic.BaseModel):
    count: int = 0
    ratio: float = 0.0
    opt_count: typing.Optional[int] = None
    opt_ratio: typing.Optional[float] = None


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
        assert form.autosave is False

    def test_title_kwarg_raises(self):
        with pytest.raises(TypeError):
            ModelForm(User, title='My Form')  # type: ignore  # title belongs to EditFormWrapper

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

    def test_from_item_unknown_kwarg_raises(self):
        with pytest.raises(TypeError):
            ModelForm.from_item(User(), title='Edit User')  # type: ignore  # title belongs to EditFormWrapper

    def test_item_property_raises_when_not_set(self):
        form = ModelForm(User)
        with pytest.raises(ValueError):
            _ = form.item

    def test_item_property_does_not_raise_for_falsy_model(self):
        class AllFalsy(pydantic.BaseModel):
            active: bool = False
            count: int = 0
        form = ModelForm(AllFalsy)
        falsy_item = AllFalsy()
        form._set_item(falsy_item)
        assert form.item is falsy_item  # must not raise even though bool(item) could be False

    def test_item_setter_wrong_type_raises(self):
        form = ModelForm(User)
        with pytest.raises(TypeError):
            form.item = 'not a model'  # type: ignore

    def test_item_setter_raises_when_adapter_bound(self):
        items = [User(name='Alice', age=30)]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm.from_adapter(User, adapter, key)
        with pytest.raises(ValueError, match='adapter-bound'):
            form.item = User(name='Bob', age=25)

    def test_item_setter_allowed_when_not_adapter_bound(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        form.item = User(name='Bob', age=25)
        assert form.item.name == 'Bob'

    def test_from_item_explicit_type(self):
        user = User(name='Alice', age=30)
        form = ModelForm.from_item(User, user)
        assert form.item is user
        assert form._item_type is User

    def test_from_item_explicit_type_wrong_type_raises(self):
        with pytest.raises(TypeError):
            ModelForm.from_item('not a type', User())  # type: ignore

    def test_from_item_explicit_type_wrong_instance_raises(self):
        with pytest.raises(TypeError):
            ModelForm.from_item(User, 'not an instance')  # type: ignore


# ---------------------------------------------------------------------------
# from_adapter
# ---------------------------------------------------------------------------

class TestFromAdapter:
    def test_from_adapter_sets_item(self):
        items = [User(name='Alice', age=30)]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm.from_adapter(User, adapter, key)
        assert form.item.name == 'Alice'

    def test_from_adapter_sets_adapter(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm.from_adapter(User, adapter, key)
        assert isinstance(form._item_adapter, BoundItem)
        assert form._item_adapter._adapter is adapter

    def test_from_adapter_non_model_type_raises(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        with pytest.raises(TypeError):
            ModelForm.from_adapter(str, adapter, key)  # type: ignore

    def test_from_adapter_unknown_kwarg_raises(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        with pytest.raises(TypeError):
            ModelForm.from_adapter(User, adapter, key, title='Test')  # type: ignore

    def test_from_adapter_returns_self(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm.from_adapter(User, adapter, key)
        assert isinstance(form, ModelForm)

    def test_from_adapter_without_key_uses_item_adapter(self, tmp_path):
        path = tmp_path / 'user.json'
        adapter = JsonAdapter(User, path)
        form = ModelForm.from_adapter(User, adapter)
        assert form.item.name == ''
        assert form._item_adapter is adapter

    def test_from_adapter_without_key_save_persists(self, tmp_path):
        path = tmp_path / 'user.json'
        adapter = JsonAdapter(User, path)
        form = ModelForm.from_adapter(User, adapter)
        form._validated_item.name = 'Via adapter'
        form.save()
        assert json.loads(path.read_text())['name'] == 'Via adapter'


# ---------------------------------------------------------------------------
# from_json
# ---------------------------------------------------------------------------

class TestFromJson:
    def test_creates_file_if_not_exist(self, tmp_path):
        path = tmp_path / 'user.json'
        ModelForm.from_json(User, path)
        assert path.exists()

    def test_loads_defaults_from_new_file(self, tmp_path):
        path = tmp_path / 'user.json'
        form = ModelForm.from_json(User, path)
        assert form.item.name == ''
        assert form.item.age == 0

    def test_loads_existing_file(self, tmp_path):
        path = tmp_path / 'user.json'
        path.write_text(json.dumps({'name': 'Bob', 'age': 25, 'active': True}))
        form = ModelForm.from_json(User, path)
        assert form.item.name == 'Bob'
        assert form.item.age == 25

    def test_non_model_type_raises(self, tmp_path):
        with pytest.raises(TypeError):
            ModelForm.from_json(str, tmp_path / 'x.json')  # type: ignore

    def test_unknown_kwarg_raises(self, tmp_path):
        path = tmp_path / 'user.json'
        with pytest.raises(TypeError):
            ModelForm.from_json(User, path, title='My Form')  # type: ignore

    def test_create_if_not_exist_false_with_existing_file(self, tmp_path):
        path = tmp_path / 'user.json'
        path.write_text(json.dumps({'name': 'Carol', 'age': 40, 'active': False}), encoding='utf-8')
        form = ModelForm.from_json(User, path, create_if_not_exist=False)
        assert form.item.name == 'Carol'

    def test_create_if_not_exist_false_missing_file_returns_defaults(self, tmp_path):
        path = tmp_path / 'user.json'
        form = ModelForm.from_json(User, path, create_if_not_exist=False)
        assert form.item == User()

    def test_save_writes_to_file(self, tmp_path):
        path = tmp_path / 'user.json'
        form = ModelForm.from_json(User, path)
        form._validated_item.name = 'Alice'
        form.save()
        data = json.loads(path.read_text(encoding='utf-8'))
        assert data['name'] == 'Alice'

    def test_autosave_flag_is_set(self, tmp_path):
        path = tmp_path / 'user.json'
        form = ModelForm.from_json(User, path, autosave=True)
        assert form.autosave is True

    def test_refresh_reloads_from_file(self, tmp_path):
        path = tmp_path / 'user.json'
        form = ModelForm.from_json(User, path)
        # externally overwrite the file
        path.write_text(json.dumps({'name': 'Dave', 'age': 50, 'active': True, 'tags': []}), encoding='utf-8')
        form.refresh()
        assert form.item.name == 'Dave'
        assert form.item.age == 50

    def test_nested_list_reference_survives_save(self, tmp_path):
        # Regression: after _save(), the nested list must still be the same
        # Python object so that a ListAdapter wrapping it stays valid.
        path = tmp_path / 'user.json'
        form = ModelForm.from_json(User, path)
        nested_list = form.item.tags  # grab reference as a nested grid adapter would
        form._validated_item.name = 'Alice'
        form.save()
        assert form.item.tags is nested_list  # same object, not a new deserialized list

    def test_nested_list_changes_visible_after_save(self, tmp_path):
        # Changes made via a nested adapter must survive the next save cycle.
        path = tmp_path / 'user.json'
        form = ModelForm.from_json(User, path)
        form.item.tags.append(Tag(label='dev'))  # simulate nested grid create
        form.save()
        data = json.loads(path.read_text(encoding='utf-8'))
        assert len(data['tags']) == 1
        assert data['tags'][0]['label'] == 'dev'

    def test_from_json_lock_field_set_on_init(self, tmp_path):
        class Timestamped(pydantic.BaseModel):
            name: str = ''
            updated_at: datetime.datetime | None = None
        path = tmp_path / 't.json'
        form = ModelForm.from_json(Timestamped, path, lock_field='updated_at')
        assert form.item.updated_at is not None

    def test_from_json_stale_lock_notifies_on_save(self, tmp_path):
        class Timestamped(pydantic.BaseModel):
            name: str = ''
            updated_at: datetime.datetime | None = None
        path = tmp_path / 't.json'
        form_a = ModelForm.from_json(Timestamped, path, lock_field='updated_at')
        form_b = ModelForm.from_json(Timestamped, path, lock_field='updated_at')
        form_a._validated_item.name = 'A'
        notify_calls = []
        with MagicMock():
            ui.notify = lambda *a, **kw: notify_calls.append((a, kw))
            form_a.save()  # advances lock
            form_b._validated_item.name = 'B'
            form_b.save()  # stale lock → ConflictError caught, notify shown, no exception
        assert any('changed' in str(args) or 'conflict' in str(args).lower() or 'reload' in str(args).lower()
                   for args, _ in notify_calls), f"Expected conflict notification, got: {notify_calls}"

    def test_from_json_created_field_set_on_init(self, tmp_path):
        class Timestamped(pydantic.BaseModel):
            name: str = ''
            created_at: datetime.datetime | None = None
        path = tmp_path / 't.json'
        form = ModelForm.from_json(Timestamped, path, created_field='created_at')
        assert form.item.created_at is not None

    def test_from_json_created_field_not_overwritten_on_save(self, tmp_path):
        import time
        class Timestamped(pydantic.BaseModel):
            name: str = ''
            created_at: datetime.datetime | None = None
        path = tmp_path / 't.json'
        form = ModelForm.from_json(Timestamped, path, created_field='created_at')
        original = form.item.created_at
        time.sleep(0.01)
        form._validated_item.name = 'changed'
        form.save()
        form.refresh()
        assert form.item.created_at == original


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------

class TestLoad:
    def test_load_from_list_adapter(self):
        items = [User(name='Bob', age=25)]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm(User)
        form.load(BoundItem(adapter, key))
        assert form.item.name == 'Bob'

    def test_load_returns_self(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm(User)
        result = form.load(BoundItem(adapter, key))
        assert result is form

    def test_load_convenience_form_with_key(self):
        items = [User(name='Carol', age=40)]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm(User)
        form.load(adapter, key)
        assert form.item.name == 'Carol'

    def test_load_convenience_binds_adapter(self):
        items = [User(name='Dan', age=50)]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm(User)
        form.load(adapter, key)
        assert form.adapter_bound


class TestAdapterBound:
    def test_adapter_bound_false_without_adapter(self):
        form = ModelForm(User)
        assert form.adapter_bound is False

    def test_adapter_bound_true_after_load(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm(User)
        form.load(BoundItem(adapter, key))
        assert form.adapter_bound is True

    def test_adapter_bound_false_from_item(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        assert form.adapter_bound is False


class TestRefresh:
    def test_refresh_without_model_raises(self):
        form = ModelForm(User)
        with pytest.raises(ValueError):
            form.refresh()

    def test_refresh_updates_validated_item(self):
        items = [User(name='Bob', age=25)]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm(User)
        form.load(BoundItem(adapter, key))
        # Modify the item in-place (simulates an external update visible through the adapter)
        items[0].name = 'Alice'
        items[0].age = 30
        form.refresh()
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
        assert form.has_validation_errors is False

    def test_invalid_current_item_sets_errors(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        form._current_item = User.model_construct(name='X' * 20, age=30)
        form._validate()
        assert form.has_validation_errors is True

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
        assert form.nonfield_validation_errors != []

    def test_nonfield_errors_empty_when_valid(self):
        form = ModelForm.from_item(CrossFieldModel(start=0, end=10))
        assert form.nonfield_validation_errors == []

    def test_has_validation_errors_includes_nonfield_errors(self):
        form = ModelForm.from_item(CrossFieldModel(start=0, end=10))
        form._current_item = CrossFieldModel.model_construct(start=10, end=5)
        form._validate()
        assert form.has_validation_errors is True

    def test_nonfield_error_element_initially_none(self):
        form = ModelForm(User)
        assert form._nonfield_error_element is None

    def test_validation_errors_empty_when_valid(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        assert form.validation_errors == {}

    def test_validation_errors_contains_field_errors(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        form._current_item = User.model_construct(name='X' * 20, age=30)
        form._validate()
        assert 'name' in form.validation_errors
        assert isinstance(form.validation_errors['name'], str)

    def test_validation_errors_returns_copy(self):
        form = ModelForm.from_item(User(name='Alice', age=30))
        errors = form.validation_errors
        errors['injected'] = 'should not affect form'
        assert 'injected' not in form.validation_errors

    def test_nonfield_validation_errors_returns_copy(self):
        form = ModelForm.from_item(CrossFieldModel(start=0, end=10))
        form._current_item = CrossFieldModel.model_construct(start=10, end=5)
        form._validate()
        errors = form.nonfield_validation_errors
        errors.clear()
        assert form.nonfield_validation_errors != []


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


# ---------------------------------------------------------------------------
# SqlModelAdapter integration
# ---------------------------------------------------------------------------

class SqlContact(sqlmodel.SQLModel, table=True):
    __tablename__ = 'test_sqlcontacts_modelform'
    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    name: str = ''
    city: str = ''


@pytest.fixture
def sql_engine():
    eng = sqlmodel.create_engine('sqlite://', connect_args={'check_same_thread': False})
    sqlmodel.SQLModel.metadata.create_all(eng)
    yield eng
    sqlmodel.SQLModel.metadata.drop_all(eng)


class TestModelFormSqlRefresh:
    def test_refresh_picks_up_background_db_change(self, sql_engine):
        adapter = SqlModelAdapter(SqlContact, sql_engine, lock_field=None)
        contact = adapter.create(SqlContact(name='Alice', city='Berlin'))
        key = adapter.key_from_item(contact)

        form = ModelForm.from_adapter(SqlContact, adapter, key)
        assert form.item.name == 'Alice'

        # Simulate a background change directly in the DB (bypassing the adapter)
        with sqlmodel.Session(sql_engine) as session:
            db_contact = session.get(SqlContact, contact.id)
            db_contact.name = 'Bob'
            db_contact.city = 'Munich'
            session.add(db_contact)
            session.commit()

        # refresh() must re-query the DB and reflect the new values
        form.refresh()
        assert form.item.name == 'Bob'
        assert form.item.city == 'Munich'


# ---------------------------------------------------------------------------
# ui.number widget value conversion
# ---------------------------------------------------------------------------

class TestNumberWidgetConversion:
    """Exercise _from_widget_value_to_current_item for the ui.number branch."""

    def _form_with_widget(self, field_name, widget_value):
        form = ModelForm.from_item(NumberModel())
        form.widgets[field_name] = MagicMock(value=widget_value)
        return form

    def test_int_field_kept_int(self):
        form = self._form_with_widget('count', 5)
        form._from_widget_value_to_current_item('count')
        assert form._current_item.count == 5
        assert type(form._current_item.count) is int

    def test_float_field_kept_float(self):
        form = self._form_with_widget('ratio', 2.5)
        form._from_widget_value_to_current_item('ratio')
        assert form._current_item.ratio == 2.5
        assert type(form._current_item.ratio) is float

    def test_optional_int_kept_int_not_float(self):
        # Optional[int] must not be coerced to float (regression: 50 -> 50.0).
        form = self._form_with_widget('opt_count', 50)
        form._from_widget_value_to_current_item('opt_count')
        assert form._current_item.opt_count == 50
        assert type(form._current_item.opt_count) is int

    def test_optional_float_kept_float(self):
        form = self._form_with_widget('opt_ratio', 1.5)
        form._from_widget_value_to_current_item('opt_ratio')
        assert type(form._current_item.opt_ratio) is float

    def test_cleared_optional_field_becomes_none(self):
        # Regression: clearing a number field yields None; must not raise int(None).
        form = self._form_with_widget('opt_count', None)
        form._current_item.opt_count = 50
        form._from_widget_value_to_current_item('opt_count')
        assert form._current_item.opt_count is None

    def test_cleared_field_empty_string_becomes_none(self):
        form = self._form_with_widget('opt_ratio', '')
        form._from_widget_value_to_current_item('opt_ratio')
        assert form._current_item.opt_ratio is None

    def test_cleared_required_int_becomes_none_for_validation(self):
        # A cleared required field maps to None so _validate() reports it,
        # rather than silently retaining a stale value.
        form = self._form_with_widget('count', None)
        form._current_item.count = 7
        form._from_widget_value_to_current_item('count')
        assert form._current_item.count is None
