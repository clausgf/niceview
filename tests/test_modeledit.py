import pydantic
import pytest
from fastapi import HTTPException

from niceview.dataadapter import ListAdapter
from niceview.modelgrid import ModelGrid
from niceview.modeledit import EditGridWrapper


class User(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=20)
    age: int = pydantic.Field(default=0, ge=0, le=120)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def items():
    return []


@pytest.fixture
def wrapper(items):
    grid = ModelGrid.from_list(User, items)
    return EditGridWrapper(grid)


@pytest.fixture
def populated_wrapper():
    items = [User(name='Alice', age=30), User(name='Bob', age=25)]
    grid = ModelGrid.from_list(User, items)
    return EditGridWrapper(grid), items


# ---------------------------------------------------------------------------
# _apply_create
# ---------------------------------------------------------------------------

class TestApplyCreate:
    def test_adds_item_to_adapter(self, wrapper, items):
        new_item = User(name='Alice', age=30)
        wrapper._apply_create(new_item)
        assert len(items) == 1

    def test_returns_created_item(self, wrapper):
        new_item = User(name='Alice', age=30)
        result = wrapper._apply_create(new_item)
        assert result.name == 'Alice'
        assert result.age == 30

    def test_create_multiple_items(self, wrapper, items):
        wrapper._apply_create(User(name='Alice', age=30))
        wrapper._apply_create(User(name='Bob', age=25))
        assert len(items) == 2

    def test_raises_on_wrong_type(self, wrapper):
        with pytest.raises(TypeError):
            wrapper._apply_create('not a model')  # type: ignore


# ---------------------------------------------------------------------------
# _apply_update
# ---------------------------------------------------------------------------

class TestApplyUpdate:
    def test_updates_item_in_adapter(self, populated_wrapper):
        wrapper, items = populated_wrapper
        original = items[0]
        key = wrapper.grid._data.key_from_item(original)
        copy = original.model_copy(deep=True)
        copy.name = 'Updated'
        wrapper._apply_update(copy, key)
        assert list(wrapper.grid._data)[0].name == 'Updated'

    def test_returns_updated_item(self, populated_wrapper):
        wrapper, items = populated_wrapper
        original = items[0]
        key = wrapper.grid._data.key_from_item(original)
        copy = original.model_copy(deep=True)
        copy.name = 'Updated'
        result = wrapper._apply_update(copy, key)
        assert result.name == 'Updated'

    def test_raises_when_key_not_found(self, wrapper):
        with pytest.raises(KeyError):
            wrapper._apply_update(User(name='Ghost'), 'nonexistent-key')


# ---------------------------------------------------------------------------
# _apply_delete
# ---------------------------------------------------------------------------

class TestApplyDelete:
    def test_removes_item_from_adapter(self, populated_wrapper):
        wrapper, items = populated_wrapper
        key = wrapper.grid._data.key_from_item(items[0])
        wrapper._apply_delete(key)
        assert len(items) == 1

    def test_removes_correct_item(self, populated_wrapper):
        wrapper, items = populated_wrapper
        key = wrapper.grid._data.key_from_item(items[0])
        wrapper._apply_delete(key)
        assert list(wrapper.grid._data)[0].name == 'Bob'

    def test_raises_when_key_not_found(self, wrapper):
        with pytest.raises(KeyError):
            wrapper._apply_delete('nonexistent-key')


# ---------------------------------------------------------------------------
# _error_msg_from_exception
# ---------------------------------------------------------------------------

class TestErrorMsgFromException:
    def test_http_exception_returns_detail(self, wrapper):
        exc = HTTPException(status_code=409, detail='Conflict')
        assert wrapper._error_msg_from_exception(exc) == 'Conflict'

    def test_generic_exception_returns_str(self, wrapper):
        exc = ValueError('something went wrong')
        assert wrapper._error_msg_from_exception(exc) == 'something went wrong'

    def test_key_error_returns_str(self, wrapper):
        exc = KeyError('missing-key')
        result = wrapper._error_msg_from_exception(exc)
        assert 'missing-key' in result


# ---------------------------------------------------------------------------
# on_change
# ---------------------------------------------------------------------------

class TestOnChange:
    def test_registers_callback(self, wrapper):
        cb = lambda e: None
        wrapper.on_change(cb)
        assert cb in wrapper._change_handlers

    def test_non_callable_raises(self, wrapper):
        with pytest.raises(TypeError):
            wrapper.on_change('not callable')  # type: ignore

    def test_returns_self(self, wrapper):
        result = wrapper.on_change(lambda e: None)
        assert result is wrapper

    def test_multiple_callbacks(self, wrapper):
        cb1 = lambda e: None
        cb2 = lambda e: None
        wrapper.on_change(cb1).on_change(cb2)
        assert cb1 in wrapper._change_handlers
        assert cb2 in wrapper._change_handlers
