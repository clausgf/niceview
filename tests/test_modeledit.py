import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pydantic
import pytest
from fastapi import HTTPException
from nicegui import ui

from niceview.dataadapter import ListAdapter
from niceview.form import ModelForm
from niceview.grid import ModelGrid
from niceview.wrapper import EditFormWrapper, EditGridWrapper


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
    def test_adds_item_to_adapter(self, wrapper):
        new_item = User(name='Alice', age=30)
        wrapper._apply_create(new_item)
        assert len(list(wrapper.grid.adapter)) == 1

    def test_returns_created_item(self, wrapper):
        new_item = User(name='Alice', age=30)
        result = wrapper._apply_create(new_item)
        assert result.name == 'Alice'
        assert result.age == 30

    def test_create_multiple_items(self, wrapper):
        wrapper._apply_create(User(name='Alice', age=30))
        wrapper._apply_create(User(name='Bob', age=25))
        assert len(list(wrapper.grid.adapter)) == 2

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
        key = wrapper.grid.adapter.key_from_item(original)
        copy = original.model_copy(deep=True)
        copy.name = 'Updated'
        wrapper._apply_update(copy, key)
        assert list(wrapper.grid.adapter)[0].name == 'Updated'

    def test_returns_updated_item(self, populated_wrapper):
        wrapper, items = populated_wrapper
        original = items[0]
        key = wrapper.grid.adapter.key_from_item(original)
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
        key = wrapper.grid.adapter.key_from_item(items[0])
        wrapper._apply_delete(key)
        assert len(list(wrapper.grid.adapter)) == 1

    def test_removes_correct_item(self, populated_wrapper):
        wrapper, items = populated_wrapper
        key = wrapper.grid.adapter.key_from_item(items[0])
        wrapper._apply_delete(key)
        assert list(wrapper.grid.adapter)[0].name == 'Bob'

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


# ---------------------------------------------------------------------------
# EditFormWrapper
# ---------------------------------------------------------------------------

class TestEditFormWrapperInit:
    def test_from_item_no_buttons_by_default(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form)
        assert w._save_button is None
        assert w._refresh_button is None

    def test_from_adapter_save_and_refresh_by_default(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm.from_adapter(User, adapter, key)
        w = EditFormWrapper(form)
        assert w._save_button == ''
        assert w._refresh_button == ''

    def test_autosave_suppresses_save_button(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm.from_adapter(User, adapter, key, autosave=True)
        w = EditFormWrapper(form)
        assert w._save_button is None

    def test_explicit_save_button_overrides_preset(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form, save_button='Save')
        assert w._save_button == 'Save'

    def test_title_default_is_none(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form)
        assert w._title is None

    def test_title_kwarg(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form, title='Edit User')
        assert w._title == 'Edit User'

    def test_unknown_kwarg_raises(self):
        form = ModelForm.from_item(User())
        with pytest.raises(TypeError):
            EditFormWrapper(form, unknown_param=True)  # type: ignore


class TestEditFormWrapperFactoryMethods:
    """
    Configuration-only tests: use the constructor (no render) to verify that
    factory method kwargs are wired correctly. Rendering is covered by
    acceptance tests in test_acceptance.py.
    """

    def _make(self, **form_kwargs):
        """Helper: create a non-rendered wrapper for configuration inspection."""
        form = ModelForm.from_item(User(), **form_kwargs)
        return EditFormWrapper(form)

    def test_from_item_creates_wrapper(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form)
        assert isinstance(w, EditFormWrapper)
        assert isinstance(w.form, ModelForm)

    def test_from_item_title_kwarg(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form, title='My Form')
        assert w._title == 'My Form'

    def test_from_item_form_kwarg_passed_through(self):
        w = self._make(autosave=True)
        assert w.form.autosave is True

    def test_from_json_shows_buttons_by_default(self, tmp_path):
        from niceview.dataadapter import JsonAdapter
        path = tmp_path / 'u.json'
        form = ModelForm(User)
        form.load(JsonAdapter(User, path))
        w = EditFormWrapper(form)
        assert w._save_button == ''
        assert w._refresh_button == ''

    def test_from_json_autosave_hides_save(self, tmp_path):
        from niceview.dataadapter import JsonAdapter
        path = tmp_path / 'u.json'
        form = ModelForm(User, autosave=True)
        form.load(JsonAdapter(User, path))
        w = EditFormWrapper(form)
        assert w._save_button is None

    def test_from_adapter_shows_buttons_by_default(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        key = adapter.key_from_item(items[0])
        form = ModelForm.from_adapter(User, adapter, key)
        w = EditFormWrapper(form)
        assert w._save_button == ''
        assert w._refresh_button == ''

    def test_on_change_delegates_to_form(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form)
        cb = lambda e: None
        w.on_change(cb)
        assert cb in w.form._change_handlers

    def test_with_repositories_delegates(self):
        form = ModelForm.from_item(User())
        w = EditFormWrapper(form)
        repos = {User: MagicMock()}
        w.with_repositories(repos)
        assert w.form._model_repositories == repos


# ---------------------------------------------------------------------------
# ModelGrid.adapter property
# ---------------------------------------------------------------------------

class TestModelGridAdapter:
    def test_adapter_returns_backing_adapter(self):
        items = [User(name='Alice', age=30)]
        adapter = ListAdapter(User, items)
        grid = ModelGrid(User, adapter)
        assert grid.adapter is adapter

    def test_adapter_same_as_internal_data(self):
        items = [User()]
        adapter = ListAdapter(User, items)
        grid = ModelGrid(User, adapter)
        assert grid.adapter is grid._data


# ---------------------------------------------------------------------------
# EditGridWrapper.refresh() — no event parameter
# ---------------------------------------------------------------------------

class TestEditGridWrapperRefresh:
    def test_refresh_takes_no_arguments(self):
        import inspect
        sig = inspect.signature(EditGridWrapper.refresh)
        params = [p for p in sig.parameters if p != 'self']
        assert params == [], f"refresh() should take no params, got {params}"

    def test_refresh_calls_update_rows(self):
        items = [User(name='Alice', age=30)]
        adapter = ListAdapter(User, items)
        grid = ModelGrid(User, adapter)
        w = EditGridWrapper(grid)
        grid.update_rows = MagicMock()
        w.refresh()
        grid.update_rows.assert_called_once()


# ---------------------------------------------------------------------------
# EditGridWrapper — create/update/delete take no event parameter (B3)
# ---------------------------------------------------------------------------

class TestEditGridWrapperDialogSignatures:
    def test_create_item_takes_no_arguments(self):
        import inspect
        sig = inspect.signature(EditGridWrapper.create_item)
        params = [p for p in sig.parameters if p != 'self']
        assert params == [], f"create_item() should take no params, got {params}"

    def test_update_item_takes_no_arguments(self):
        import inspect
        sig = inspect.signature(EditGridWrapper.update_item)
        params = [p for p in sig.parameters if p != 'self']
        assert params == [], f"update_item() should take no params, got {params}"

    def test_delete_item_takes_no_arguments(self):
        import inspect
        sig = inspect.signature(EditGridWrapper.delete_item)
        params = [p for p in sig.parameters if p != 'self']
        assert params == [], f"delete_item() should take no params, got {params}"

    def test_private_on_create_clicked_has_event_param(self):
        import inspect
        sig = inspect.signature(EditGridWrapper._on_create_clicked)
        params = [p for p in sig.parameters if p != 'self']
        assert 'event' in params

    def test_private_on_delete_clicked_has_event_param(self):
        import inspect
        sig = inspect.signature(EditGridWrapper._on_delete_clicked)
        params = [p for p in sig.parameters if p != 'self']
        assert 'event' in params


# ---------------------------------------------------------------------------
# EditGridWrapper.__init__ — rowSelection validation (f-string bug fix)
# ---------------------------------------------------------------------------

class TestEditGridWrapperRowSelectionValidation:
    def test_multiple_row_selection_raises(self):
        grid = ModelGrid.from_list(User, [], rowSelection='multiple')
        with pytest.raises(ValueError):
            EditGridWrapper(grid)

    def test_multiple_row_selection_error_includes_value(self):
        grid = ModelGrid.from_list(User, [], rowSelection='multiple')
        with pytest.raises(ValueError, match='multiple'):
            EditGridWrapper(grid)

    def test_single_row_selection_does_not_raise(self):
        grid = ModelGrid.from_list(User, [], rowSelection='single')
        wrapper = EditGridWrapper(grid)
        assert wrapper.grid._rowSelection == 'single'

    def test_none_row_selection_does_not_raise(self):
        grid = ModelGrid.from_list(User, [])
        wrapper = EditGridWrapper(grid)
        assert wrapper.grid._rowSelection == 'single'


# ---------------------------------------------------------------------------
# EditGridWrapper.update_item — change handlers not fired on adapter failure
# ---------------------------------------------------------------------------

class TestEditGridWrapperUpdateItemOnFailure:
    def setup_method(self):
        items = [User(name='Alice', age=30)]
        grid = ModelGrid.from_list(User, items)
        self.wrapper = EditGridWrapper(grid)
        self.wrapper._get_selected_row_key = AsyncMock(return_value='key-0')
        self.wrapper.grid.adapter.read = MagicMock(return_value=User(name='Alice', age=30))
        self.wrapper.default_edit_create_handler = AsyncMock(return_value=True)
        self.wrapper.grid.update_rows = MagicMock()

    def test_change_handlers_not_called_when_apply_raises(self):
        handler = MagicMock()
        self.wrapper.on_change(handler)
        self.wrapper._apply_update = MagicMock(side_effect=RuntimeError('DB error'))

        with patch.object(ui, 'notify'):
            asyncio.run(self.wrapper.update_item())

        handler.assert_not_called()

    def test_update_rows_still_called_when_apply_raises(self):
        self.wrapper._apply_update = MagicMock(side_effect=RuntimeError('DB error'))

        with patch.object(ui, 'notify'):
            asyncio.run(self.wrapper.update_item())

        self.wrapper.grid.update_rows.assert_called()

    def test_change_handlers_called_on_success(self):
        handler = MagicMock()
        self.wrapper.on_change(handler)
        self.wrapper._apply_update = MagicMock(return_value=User(name='Alice', age=30))
        self.wrapper.grid.adapter.key_from_item = MagicMock(return_value='key-0')
        self.wrapper.grid.widget = MagicMock()
        self.wrapper.grid.widget.client = MagicMock()

        with patch.object(ui, 'notify'):
            asyncio.run(self.wrapper.update_item())

        handler.assert_called_once()


# ---------------------------------------------------------------------------
# EditGridWrapper.delete_item — change handlers not fired on adapter failure
# ---------------------------------------------------------------------------

class TestEditGridWrapperDeleteItemOnFailure:
    def setup_method(self):
        items = [User(name='Alice', age=30)]
        grid = ModelGrid.from_list(User, items)
        self.wrapper = EditGridWrapper(grid)
        self.wrapper._get_selected_row_key = AsyncMock(return_value='key-0')
        self.wrapper.grid.update_rows = MagicMock()

    def test_change_handlers_not_called_when_apply_raises(self):
        handler = MagicMock()
        self.wrapper.on_change(handler)
        self.wrapper._apply_delete = MagicMock(side_effect=RuntimeError('DB error'))

        with patch('niceview.wrapper.submit_dialog', new=AsyncMock(return_value=True)), \
             patch.object(ui, 'notify'):
            asyncio.run(self.wrapper.delete_item())

        handler.assert_not_called()

    def test_update_rows_still_called_when_apply_raises(self):
        self.wrapper._apply_delete = MagicMock(side_effect=RuntimeError('DB error'))

        with patch('niceview.wrapper.submit_dialog', new=AsyncMock(return_value=True)), \
             patch.object(ui, 'notify'):
            asyncio.run(self.wrapper.delete_item())

        self.wrapper.grid.update_rows.assert_called()

    def test_change_handlers_called_on_success(self):
        handler = MagicMock()
        self.wrapper.on_change(handler)
        self.wrapper.grid.widget = MagicMock()
        self.wrapper.grid.widget.client = MagicMock()
        self.wrapper._apply_delete = MagicMock()

        with patch('niceview.wrapper.submit_dialog', new=AsyncMock(return_value=True)), \
             patch.object(ui, 'notify'):
            asyncio.run(self.wrapper.delete_item())

        handler.assert_called_once()
