import datetime
import json
import pytest
import pydantic
from pathlib import Path
from typing import Annotated

from niceview.dataadapter import ConflictError, ListAdapter, JsonAdapter, JsonListAdapter, DirectoryAdapter, FileEntry
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit


class Item(pydantic.BaseModel):
    name: str = ''
    value: int = 0

    def __str__(self):
        return self.name


class TimestampedItem(pydantic.BaseModel):
    name: str = ''
    created_at: datetime.datetime | None = None


# ---------------------------------------------------------------------------
# ListAdapter
# ---------------------------------------------------------------------------

class TestListAdapterRead:
    def setup_method(self):
        self.items = [Item(name='a', value=1), Item(name='b', value=2), Item(name='c', value=3)]
        self.adapter = ListAdapter(Item, self.items)

    def test_read_first(self):
        key = self.adapter.key_from_item(self.items[0])
        assert self.adapter.read(key).name == 'a'

    def test_read_last(self):
        key = self.adapter.key_from_item(self.items[2])
        assert self.adapter.read(key).name == 'c'

    def test_read_middle(self):
        key = self.adapter.key_from_item(self.items[1])
        assert self.adapter.read(key).name == 'b'

    def test_read_unknown_key_raises(self):
        with pytest.raises(KeyError):
            self.adapter.read('not-a-valid-key')


class TestListAdapterCreate:
    def setup_method(self):
        self.items = [Item(name='a')]
        self.adapter = ListAdapter(Item, self.items)

    def test_create_appends_item(self):
        new_item = Item(name='z', value=99)
        self.adapter.create(new_item)
        assert len(self.adapter._items) == 2
        assert self.adapter._items[-1].name == 'z'

    def test_create_returns_item(self):
        new_item = Item(name='z')
        result = self.adapter.create(new_item)
        assert result is new_item

    def test_create_wrong_type_raises(self):
        with pytest.raises(TypeError):
            self.adapter.create("not an Item")  # type: ignore

    def test_created_item_readable_by_key(self):
        new_item = Item(name='z')
        self.adapter.create(new_item)
        key = self.adapter.key_from_item(new_item)
        assert self.adapter.read(key).name == 'z'


class TestListAdapterUpdate:
    def setup_method(self):
        self.items = [Item(name='a', value=1), Item(name='b', value=2)]
        self.adapter = ListAdapter(Item, self.items)

    def test_update_modifies_inplace(self):
        original = self.items[0]
        original.name = 'X'
        original.value = 99
        self.adapter.update(original)
        assert self.adapter._items[0].name == 'X'

    def test_update_returns_item(self):
        original = self.items[0]
        original.name = 'X'
        result = self.adapter.update(original)
        assert result is original

    def test_update_unknown_item_raises(self):
        with pytest.raises(KeyError):
            self.adapter.update(Item())  # Item() not registered in adapter

    def test_update_same_object_inplace(self):
        self.items[0].name = 'modified'
        result = self.adapter.update(self.items[0])
        assert result.name == 'modified'


class TestListAdapterDelete:
    def setup_method(self):
        self.items = [Item(name='a'), Item(name='b'), Item(name='c')]
        self.adapter = ListAdapter(Item, self.items)

    def test_delete_removes_item(self):
        key = self.adapter.key_from_item(self.items[1])
        self.adapter.delete(key)
        assert len(self.adapter._items) == 2
        assert self.adapter._items[0].name == 'a'
        assert self.adapter._items[1].name == 'c'

    def test_delete_unknown_key_raises(self):
        with pytest.raises(KeyError):
            self.adapter.delete('not-a-valid-key')

    def test_key_stable_after_delete(self):
        # key of 'c' (originally at index 2) stays valid after deleting 'b' (index 1)
        key_c = self.adapter.key_from_item(self.items[2])
        self.adapter.delete(self.adapter.key_from_item(self.items[1]))
        assert self.adapter.read(key_c).name == 'c'


class TestListAdapterReactive:
    def test_on_change_fires_on_create_with_plain_list(self):
        adapter = ListAdapter(Item, [])
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.create(Item(name='x'))
        assert called == [True]

    def test_on_change_fires_on_delete_with_plain_list(self):
        item = Item(name='x')
        adapter = ListAdapter(Item, [item])
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.delete(adapter.key_from_item(item))
        assert called == [True]

    def test_on_change_fires_on_update_with_plain_list(self):
        item = Item(name='x')
        adapter = ListAdapter(Item, [item])
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        item.name = 'y'
        adapter.update(item)
        assert called == [True]

    def test_on_change_fires_on_create_with_observable_list(self):
        from nicegui.observables import ObservableList
        adapter = ListAdapter(Item, ObservableList([]))
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.create(Item(name='x'))
        assert called == [True]

    def test_on_change_fires_on_delete_with_observable_list(self):
        from nicegui.observables import ObservableList
        item = Item(name='x')
        adapter = ListAdapter(Item, ObservableList([item]))
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.delete(adapter.key_from_item(item))
        assert called == [True]

    def test_on_change_fires_on_update_with_observable_list(self):
        from nicegui.observables import ObservableList
        item = Item(name='x')
        adapter = ListAdapter(Item, ObservableList([item]))
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        item.name = 'y'
        adapter.update(item)
        assert called == [True]

    def test_on_change_no_double_fire_with_observable_list(self):
        from nicegui.observables import ObservableList
        adapter = ListAdapter(Item, ObservableList([]))
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.create(Item(name='x'))
        assert called == [True]  # exactly once, not twice

    def test_on_change_fires_on_direct_observable_list_mutation(self):
        from nicegui.observables import ObservableList
        obs: ObservableList = ObservableList([])
        adapter = ListAdapter(Item, obs)
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        obs.append(Item(name='direct'))  # bypass adapter
        assert called == [True]

    def test_isinstance_reactive_adapter_with_observable_list(self):
        from nicegui.observables import ObservableList
        from niceview.dataadapter import ReactiveAdapter
        adapter = ListAdapter(Item, ObservableList([]))
        assert isinstance(adapter, ReactiveAdapter)

    def test_isinstance_reactive_adapter_with_plain_list(self):
        from niceview.dataadapter import ReactiveAdapter
        adapter = ListAdapter(Item, [])
        assert isinstance(adapter, ReactiveAdapter)


class TestListAdapterKeys:
    def setup_method(self):
        self.items = [Item(name='a'), Item(name='b')]
        self.adapter = ListAdapter(Item, self.items)

    def test_key_from_item_is_string(self):
        key = self.adapter.key_from_item(self.items[0])
        assert isinstance(key, str)

    def test_key_from_item_unique_per_object(self):
        key_a = self.adapter.key_from_item(self.items[0])
        key_b = self.adapter.key_from_item(self.items[1])
        assert key_a != key_b

    def test_iter_yields_all_items(self):
        result = list(self.adapter)
        assert len(result) == 2
        assert result[0].name == 'a'

    def test_query_all_strs_returns_valid_keys(self):
        pairs = list(self.adapter._query_all_strs())
        assert len(pairs) == 2
        for key, _ in pairs:
            assert self.adapter.read(key) is not None

    def test_query_all_strs_str_is_item_str(self):
        pairs = list(self.adapter._query_all_strs())
        names = [s for _, s in pairs]
        assert names == ['a', 'b']


# ---------------------------------------------------------------------------
# JsonAdapter
# ---------------------------------------------------------------------------

class TestJsonAdapter:
    def test_create_if_not_exist(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(Item, path, create_if_not_exist=True)
        assert path.exists()

    def test_created_file_has_default_values(self, tmp_path):
        path = tmp_path / 'data.json'
        JsonAdapter(Item, path, create_if_not_exist=True)
        data = json.loads(path.read_text())
        assert data == {'name': '', 'value': 0}

    def test_no_create_if_not_exist_does_not_create_file(self, tmp_path):
        path = tmp_path / 'data.json'
        JsonAdapter(Item, path, create_if_not_exist=False)
        assert not path.exists()

    def test_read_existing_file(self, tmp_path):
        path = tmp_path / 'data.json'
        path.write_text(json.dumps({'name': 'hello', 'value': 42}))
        adapter = JsonAdapter(Item, path, create_if_not_exist=False)
        item = adapter.read()
        assert item.name == 'hello'
        assert item.value == 42

    def test_save_writes_to_file(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(Item, path, create_if_not_exist=True)
        adapter.save(Item(name='updated', value=7))
        data = json.loads(path.read_text())
        assert data['name'] == 'updated'
        assert data['value'] == 7

    def test_save_returns_same_object(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(Item, path, create_if_not_exist=True)
        item = Item(name='x', value=3)
        result = adapter.save(item)
        assert result is item  # same object — preserves references held by nested widgets

    def test_path_is_directory_raises(self, tmp_path):
        with pytest.raises(ValueError):
            JsonAdapter(Item, tmp_path, create_if_not_exist=False)

    def test_invalid_item_type_raises(self, tmp_path):
        path = tmp_path / 'data.json'
        with pytest.raises(TypeError):
            JsonAdapter(str, path)  # type: ignore

    def test_read_missing_file_raises(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(Item, path, create_if_not_exist=False, strict=True)
        with pytest.raises(FileNotFoundError):
            adapter.read()

    def test_read_invalid_json_raises(self, tmp_path):
        path = tmp_path / 'data.json'
        path.write_text('not valid json', encoding='utf-8')
        adapter = JsonAdapter(Item, path, create_if_not_exist=False, strict=True)
        with pytest.raises(Exception):
            adapter.read()

    def test_save_is_atomic(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(Item, path, create_if_not_exist=True)
        adapter.save(Item(name='v2', value=2))
        # temp file must not linger
        assert not path.with_name(path.name + '.tmp').exists()
        assert path.exists()

    def test_create_if_not_exist_false_with_existing_file(self, tmp_path):
        path = tmp_path / 'data.json'
        path.write_text('{"name": "existing", "value": 7}', encoding='utf-8')
        adapter = JsonAdapter(Item, path, create_if_not_exist=False)
        item = adapter.read()
        assert item.name == 'existing'


class TestJsonAdapterLockField:
    def test_lock_field_set_on_save(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, lock_field='created_at')
        item = adapter.read()
        assert item.created_at is not None

    def test_lock_field_updated_on_save(self, tmp_path):
        import time
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, lock_field='created_at')
        item = adapter.read()
        old_ts = item.created_at
        time.sleep(0.01)
        updated = adapter.save(item)
        assert updated.created_at > old_ts

    def test_stale_lock_raises(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, lock_field='created_at')
        item_a = adapter.read()
        item_b = adapter.read()
        adapter.save(item_a)   # A saves first → lock_field advances
        with pytest.raises(ConflictError):
            adapter.save(item_b)   # B has stale lock → rejected

    def test_fresh_save_after_reload_succeeds(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, lock_field='created_at')
        item_a = adapter.read()
        adapter.save(item_a)
        item_b = adapter.read()   # reload → fresh lock value
        adapter.save(item_b)      # must succeed

    def test_none_lock_field_in_file_does_not_raise(self, tmp_path):
        # lock_field is None in the file → no conflict (missing lock data = no locking)
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, lock_field='created_at')
        item = adapter.read()
        item.created_at = None  # simulate: field was null in the file
        adapter.save(item)  # must not raise ConflictError

    def test_none_lock_field_on_item_does_not_raise(self, tmp_path):
        # item has no lock value yet (freshly constructed) → no conflict
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, lock_field='created_at')
        item = adapter.read()
        item.created_at = None  # item has no timestamp
        adapter.save(item)  # must not raise

    def test_corrupted_file_raises_storage_error(self, tmp_path):
        from niceview.dataadapter import StorageError
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, lock_field='created_at', strict=True)
        path.write_text('not valid json', encoding='utf-8')
        item = TimestampedItem()
        with pytest.raises(StorageError):
            adapter.save(item)

    def test_invalid_lock_field_raises(self, tmp_path):
        path = tmp_path / 'data.json'
        with pytest.raises(ValueError, match='does not have a field named'):
            JsonAdapter(Item, path, lock_field='nonexistent')


class TestJsonAdapterCreatedField:
    def test_created_field_set_on_first_save(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, created_field='created_at')
        item = adapter.read()
        assert item.created_at is not None

    def test_created_field_not_overwritten_on_subsequent_save(self, tmp_path):
        import time
        path = tmp_path / 'data.json'
        adapter = JsonAdapter(TimestampedItem, path, created_field='created_at')
        item = adapter.read()
        original_ts = item.created_at
        time.sleep(0.01)
        adapter.save(item)
        reloaded = adapter.read()
        assert reloaded.created_at == original_ts

    def test_created_and_lock_field_together(self, tmp_path):
        import time
        path = tmp_path / 'data.json'

        class Entry(pydantic.BaseModel):
            name: str = ''
            created_at: datetime.datetime | None = None
            updated_at: datetime.datetime | None = None

        adapter = JsonAdapter(Entry, path, lock_field='updated_at', created_field='created_at')
        item = adapter.read()
        assert item.created_at is not None
        assert item.updated_at is not None
        original_created = item.created_at
        time.sleep(0.01)
        adapter.save(item)
        reloaded = adapter.read()
        assert reloaded.created_at == original_created   # unchanged
        assert reloaded.updated_at > original_created    # advanced

    def test_invalid_created_field_raises(self, tmp_path):
        path = tmp_path / 'data.json'
        with pytest.raises(ValueError, match='does not have a field named'):
            JsonAdapter(Item, path, created_field='nonexistent')


# ---------------------------------------------------------------------------
# JsonListAdapter
# ---------------------------------------------------------------------------

class TestJsonListAdapterInit:
    def test_creates_empty_file_if_not_exist(self, tmp_path):
        path = tmp_path / 'items.json'
        JsonListAdapter(Item, path)
        assert path.exists()
        assert json.loads(path.read_text()) == []

    def test_loads_existing_items(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'a', 'value': 1}, {'name': 'b', 'value': 2}]), encoding='utf-8')
        adapter = JsonListAdapter(Item, path)
        items = list(adapter)
        assert len(items) == 2
        assert items[0].name == 'a'
        assert items[1].name == 'b'

    def test_create_if_not_exist_false_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            JsonListAdapter(Item, tmp_path / 'missing.json', create_if_not_exist=False)

    def test_create_if_not_exist_false_with_existing_file(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'x', 'value': 9}]), encoding='utf-8')
        adapter = JsonListAdapter(Item, path, create_if_not_exist=False)
        assert list(adapter)[0].name == 'x'

    def test_path_is_directory_raises(self, tmp_path):
        with pytest.raises(ValueError):
            JsonListAdapter(Item, tmp_path)

    def test_invalid_item_type_raises(self, tmp_path):
        with pytest.raises(TypeError):
            JsonListAdapter(str, tmp_path / 'items.json')  # type: ignore


class TestJsonListAdapterCreate:
    def test_create_appends_and_persists(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(Item, path)
        adapter.create(Item(name='z', value=99))
        raw = json.loads(path.read_text(encoding='utf-8'))
        assert len(raw) == 1
        assert raw[0]['name'] == 'z'

    def test_create_returns_item(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(Item, path)
        new_item = Item(name='z')
        result = adapter.create(new_item)
        assert result is new_item

    def test_create_readable_by_key(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(Item, path)
        new_item = adapter.create(Item(name='z'))
        key = adapter.key_from_item(new_item)
        assert adapter.read(key).name == 'z'


class TestJsonListAdapterUpdate:
    def setup_method(self):
        pass

    def test_update_persists_to_file(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'a', 'value': 1}]), encoding='utf-8')
        adapter = JsonListAdapter(Item, path)
        item = list(adapter)[0]
        item.name = 'X'
        item.value = 99
        adapter.update(item)
        raw = json.loads(path.read_text(encoding='utf-8'))
        assert raw[0]['name'] == 'X'

    def test_update_returns_item(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'a', 'value': 1}]), encoding='utf-8')
        adapter = JsonListAdapter(Item, path)
        item = list(adapter)[0]
        item.name = 'X'
        result = adapter.update(item)
        assert result is item


class TestJsonListAdapterDelete:
    def test_delete_removes_and_persists(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'a', 'value': 1}, {'name': 'b', 'value': 2}]), encoding='utf-8')
        adapter = JsonListAdapter(Item, path)
        items = list(adapter)
        key = adapter.key_from_item(items[0])
        adapter.delete(key)
        raw = json.loads(path.read_text(encoding='utf-8'))
        assert len(raw) == 1
        assert raw[0]['name'] == 'b'

    def test_key_stable_after_delete(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'a', 'value': 1}, {'name': 'b', 'value': 2}]), encoding='utf-8')
        adapter = JsonListAdapter(Item, path)
        items = list(adapter)
        key_b = adapter.key_from_item(items[1])
        adapter.delete(adapter.key_from_item(items[0]))
        assert adapter.read(key_b).name == 'b'


class TestJsonListAdapterReload:
    def test_reload_picks_up_external_changes(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(Item, path)
        adapter.create(Item(name='a'))
        # external write
        path.write_text(json.dumps([{'name': 'external', 'value': 42}]), encoding='utf-8')
        adapter.reload()
        assert list(adapter)[0].name == 'external'

    def test_reload_replaces_all_items(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'a'}, {'name': 'b'}]), encoding='utf-8')
        adapter = JsonListAdapter(Item, path)
        path.write_text(json.dumps([{'name': 'only'}]), encoding='utf-8')
        adapter.reload()
        assert len(list(adapter)) == 1

    def test_atomic_write_no_tmp_left(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(Item, path)
        adapter.create(Item(name='x'))
        assert not path.with_name(path.name + '.tmp').exists()


# ---------------------------------------------------------------------------
# ListAdapter created_field
# ---------------------------------------------------------------------------

class TestListAdapterCreatedField:
    def test_created_field_set_on_create(self):
        adapter = ListAdapter(TimestampedItem, [], created_field='created_at')
        item = adapter.create(TimestampedItem(name='x'))
        assert item.created_at is not None

    def test_created_field_is_utc(self):
        before = datetime.datetime.now(datetime.timezone.utc)
        adapter = ListAdapter(TimestampedItem, [], created_field='created_at')
        item = adapter.create(TimestampedItem(name='x'))
        after = datetime.datetime.now(datetime.timezone.utc)
        ts = item.created_at.replace(tzinfo=datetime.timezone.utc)
        assert before <= ts <= after

    def test_created_field_not_overwritten_on_update(self):
        import time
        adapter = ListAdapter(TimestampedItem, [], created_field='created_at')
        item = adapter.create(TimestampedItem(name='x'))
        original = item.created_at
        time.sleep(0.01)
        item.name = 'changed'
        adapter.update(item)
        assert item.created_at == original

    def test_created_field_invalid_name_raises(self):
        with pytest.raises(ValueError, match='does not have a field named'):
            ListAdapter(TimestampedItem, [], created_field='nonexistent')

    def test_created_field_none_by_default(self):
        adapter = ListAdapter(TimestampedItem, [])
        item = adapter.create(TimestampedItem(name='x'))
        assert item.created_at is None


class TestJsonListAdapterCreatedField:
    def test_created_field_set_on_create(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(TimestampedItem, path, created_field='created_at')
        item = adapter.create(TimestampedItem(name='x'))
        assert item.created_at is not None

    def test_created_field_persisted_to_json(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(TimestampedItem, path, created_field='created_at')
        adapter.create(TimestampedItem(name='x'))
        raw = json.loads(path.read_text())
        assert raw[0]['created_at'] is not None

    def test_created_field_survives_reload(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(TimestampedItem, path, created_field='created_at')
        item = adapter.create(TimestampedItem(name='x'))
        original_ts = item.created_at
        adapter2 = JsonListAdapter(TimestampedItem, path, created_field='created_at')
        reloaded = list(adapter2)[0]
        assert reloaded.created_at is not None
        assert reloaded.created_at.replace(tzinfo=datetime.timezone.utc) == original_ts.replace(tzinfo=datetime.timezone.utc)


# ---------------------------------------------------------------------------
# DirectoryAdapter
# ---------------------------------------------------------------------------

class TestDirectoryAdapterInit:
    def test_path_not_a_directory_raises(self, tmp_path):
        not_a_dir = tmp_path / 'file.txt'
        not_a_dir.write_text('x')
        with pytest.raises(ValueError):
            DirectoryAdapter(not_a_dir)

    def test_empty_directory_iterates_empty(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        assert list(adapter) == []


class TestDirectoryAdapterCreate:
    def test_create_without_item_generates_untitled_name(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        assert entry.name == 'untitled-01'
        assert (tmp_path / 'untitled-01.json').exists()

    def test_create_generates_zero_padded_incrementing_names(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        names = [adapter.create().name for _ in range(3)]
        assert names == ['untitled-01', 'untitled-02', 'untitled-03']

    def test_create_skips_existing_untitled_names(self, tmp_path):
        (tmp_path / 'untitled-01.json').write_text('{}')
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        assert entry.name == 'untitled-02'

    def test_create_writes_default_content(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path, default_content='[]')
        entry = adapter.create()
        assert (tmp_path / f'{entry.name}.json').read_text(encoding='utf-8') == '[]'

    def test_create_default_content_callable(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path, default_content=lambda: '{"a": 1}')
        entry = adapter.create()
        assert (tmp_path / f'{entry.name}.json').read_text(encoding='utf-8') == '{"a": 1}'

    def test_create_with_explicit_name(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create(FileEntry(name='screen1', mtime=datetime.datetime.now(datetime.timezone.utc), size=0))
        assert entry.name == 'screen1'
        assert (tmp_path / 'screen1.json').exists()

    def test_create_existing_name_raises(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        adapter.create(FileEntry(name='dup', mtime=datetime.datetime.now(datetime.timezone.utc), size=0))
        with pytest.raises(ValueError):
            adapter.create(FileEntry(name='dup', mtime=datetime.datetime.now(datetime.timezone.utc), size=0))

    def test_create_notifies_on_change(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.create()
        assert called == [True]

    def test_suffix_is_configurable(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path, suffix='.txt')
        entry = adapter.create()
        assert (tmp_path / f'{entry.name}.txt').exists()

    def test_create_strips_user_typed_suffix(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create(FileEntry(name='note.json', mtime=datetime.datetime.now(datetime.timezone.utc), size=0))
        assert entry.name == 'note'
        assert (tmp_path / 'note.json').exists()
        assert not (tmp_path / 'note.json.json').exists()


class TestDirectoryAdapterRead:
    def test_read_returns_metadata(self, tmp_path):
        (tmp_path / 'a.json').write_text('hello')
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.read('a')
        assert entry.name == 'a'
        assert entry.size == len('hello')

    def test_read_missing_raises_keyerror(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        with pytest.raises(KeyError):
            adapter.read('missing')

    def test_key_from_item(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        assert adapter.key_from_item(entry) == entry.name


class TestDirectoryAdapterDelete:
    def test_delete_removes_file(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        adapter.delete(entry.name)
        assert not (tmp_path / f'{entry.name}.json').exists()

    def test_delete_missing_raises_keyerror(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        with pytest.raises(KeyError):
            adapter.delete('missing')

    def test_delete_notifies_on_change(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.delete(entry.name)
        assert called == [True]


class TestDirectoryAdapterRename:
    def test_rename_renames_file(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        new_key = adapter.rename(entry.name, 'renamed')
        assert new_key == 'renamed'
        assert not (tmp_path / f'{entry.name}.json').exists()
        assert (tmp_path / 'renamed.json').exists()

    def test_rename_preserves_content(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path, default_content='payload')
        entry = adapter.create()
        adapter.rename(entry.name, 'renamed')
        assert (tmp_path / 'renamed.json').read_text(encoding='utf-8') == 'payload'

    def test_rename_missing_raises_keyerror(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        with pytest.raises(KeyError):
            adapter.rename('missing', 'new')

    def test_rename_to_existing_name_raises(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        a = adapter.create()
        b = adapter.create()
        with pytest.raises(ValueError):
            adapter.rename(a.name, b.name)

    def test_rename_strips_user_typed_suffix(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        new_key = adapter.rename(entry.name, 'note.json')
        assert new_key == 'note'
        assert (tmp_path / 'note.json').exists()
        assert not (tmp_path / 'note.json.json').exists()

    def test_rename_notifies_on_change(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        entry = adapter.create()
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.rename(entry.name, 'renamed')
        assert called == [True]


class TestDirectoryAdapterKeyValidation:
    def test_path_separator_in_key_raises(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        with pytest.raises(ValueError):
            adapter.read('../secret')

    def test_empty_key_raises(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        with pytest.raises(ValueError):
            adapter.read('')


class TestDirectoryAdapterItems:
    def test_items_sorted_by_name(self, tmp_path):
        adapter = DirectoryAdapter(tmp_path)
        adapter.create(FileEntry(name='b', mtime=datetime.datetime.now(datetime.timezone.utc), size=0))
        adapter.create(FileEntry(name='a', mtime=datetime.datetime.now(datetime.timezone.utc), size=0))
        names = [entry.name for entry in adapter]
        assert names == ['a', 'b']

    def test_only_matching_suffix_listed(self, tmp_path):
        (tmp_path / 'other.txt').write_text('x')
        adapter = DirectoryAdapter(tmp_path)
        adapter.create()
        names = [entry.name for entry in adapter]
        assert names == ['untitled-01']


# ---------------------------------------------------------------------------
# ModelGrid.from_json / ModelGridInlineEdit.from_json
# ---------------------------------------------------------------------------
# ModelGrid.from_list / ModelGridInlineEdit.from_list
# ---------------------------------------------------------------------------

class TestModelGridFromAdapter:
    def test_from_adapter_creates_grid(self):
        items = [Item(name='a')]
        adapter = ListAdapter(Item, items)
        grid = ModelGrid.from_adapter(Item, adapter)
        assert isinstance(grid, ModelGrid)
        assert grid._data is adapter

    def test_inline_edit_from_adapter_creates_correct_type(self):
        items = [Item(name='a')]
        adapter = ListAdapter(Item, items)
        grid = ModelGridInlineEdit.from_adapter(Item, adapter)
        assert isinstance(grid, ModelGridInlineEdit)


class TestModelGridFromList:
    def test_from_list_creates_grid(self):
        items = [Item(name='a'), Item(name='b')]
        grid = ModelGrid.from_list(Item, items)
        assert isinstance(grid, ModelGrid)

    def test_from_list_adapter_is_list_adapter(self):
        items = [Item(name='a')]
        grid = ModelGrid.from_list(Item, items)
        assert isinstance(grid._data, ListAdapter)

    def test_from_list_empty_list_allowed(self):
        grid = ModelGrid.from_list(Item, [])
        assert list(grid._data) == []

    def test_from_list_items_accessible(self):
        items = [Item(name='x', value=7)]
        grid = ModelGrid.from_list(Item, items)
        assert list(grid._data)[0].name == 'x'

    def test_inline_edit_from_list_creates_correct_type(self):
        items = [Item(name='a')]
        grid = ModelGridInlineEdit.from_list(Item, items)
        assert isinstance(grid, ModelGridInlineEdit)
        assert isinstance(grid._data, ListAdapter)


# ---------------------------------------------------------------------------

class TestModelGridFromJson:
    def test_from_json_creates_grid(self, tmp_path):
        path = tmp_path / 'items.json'
        grid = ModelGrid.from_json(Item, path)
        assert isinstance(grid, ModelGrid)

    def test_from_json_adapter_is_json_list(self, tmp_path):
        path = tmp_path / 'items.json'
        grid = ModelGrid.from_json(Item, path)
        assert isinstance(grid._data, JsonListAdapter)

    def test_from_json_creates_file(self, tmp_path):
        path = tmp_path / 'items.json'
        ModelGrid.from_json(Item, path)
        assert path.exists()

    def test_from_json_loads_existing_items(self, tmp_path):
        path = tmp_path / 'items.json'
        path.write_text(json.dumps([{'name': 'a', 'value': 1}]), encoding='utf-8')
        grid = ModelGrid.from_json(Item, path)
        assert list(grid._data)[0].name == 'a'

    def test_inline_edit_from_json_creates_correct_type(self, tmp_path):
        path = tmp_path / 'items.json'
        grid = ModelGridInlineEdit.from_json(Item, path)
        assert isinstance(grid, ModelGridInlineEdit)
        assert isinstance(grid._data, JsonListAdapter)

    def test_from_json_missing_file_raises_when_no_create(self, tmp_path):
        path = tmp_path / 'items.json'
        with pytest.raises(FileNotFoundError):
            ModelGrid.from_json(Item, path, create_if_not_exist=False)


# ---------------------------------------------------------------------------
# ModelGrid.__init__ validation
# ---------------------------------------------------------------------------

class TestModelGridInit:
    def test_non_type_raises_type_error(self):
        with pytest.raises(TypeError):
            ModelGrid('not_a_type', ListAdapter(Item, []))  # type: ignore[arg-type]

    def test_non_model_subclass_raises_type_error(self):
        with pytest.raises(TypeError, match='item_type'):
            ModelGrid(str, ListAdapter(Item, []))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ModelGrid.update_rows
# ---------------------------------------------------------------------------

class TestModelGridUpdateRows:
    def test_rows_reflect_adapter_items(self):
        items = [Item(name='alice', value=1), Item(name='bob', value=2)]
        grid = ModelGrid.from_list(Item, items)
        grid._rows = []
        grid.widget = None
        grid.update_rows()
        assert [r['name'] for r in grid._rows] == ['alice', 'bob']

    def test_clears_stale_rows(self):
        items = [Item(name='x', value=0)]
        grid = ModelGrid.from_list(Item, items)
        grid._rows = [{'__ui_row_key': 'old', 'name': 'stale'}]
        grid.widget = None
        grid.update_rows()
        assert len(grid._rows) == 1
        assert grid._rows[0]['name'] == 'x'

    def test_empty_adapter_produces_no_rows(self):
        grid = ModelGrid.from_list(Item, [])
        grid._rows = []
        grid.widget = None
        grid.update_rows()
        assert grid._rows == []

    def test_row_key_is_present(self):
        items = [Item(name='a')]
        grid = ModelGrid.from_list(Item, items)
        grid._rows = []
        grid.widget = None
        grid.update_rows()
        assert '__ui_row_key' in grid._rows[0]

    def test_update_rows_works_before_render(self):
        # Regression: _rows was only initialized in render(), so calling
        # update_rows() first raised AttributeError.
        grid = ModelGrid.from_list(Item, [Item(name='early', value=1)])
        grid.update_rows()
        assert [r['name'] for r in grid._rows] == ['early']


# ---------------------------------------------------------------------------
# ModelGridInlineEdit initialization
# ---------------------------------------------------------------------------

class TestModelGridInlineEditInit:
    def test_cells_are_editable_by_default(self):
        grid = ModelGridInlineEdit.from_list(Item, [])
        assert grid._defaultColDef.get('editable') is True

    def test_change_handlers_start_empty(self):
        grid = ModelGridInlineEdit.from_list(Item, [])
        assert grid._change_handlers == []

    def test_on_change_registers_callback(self):
        grid = ModelGridInlineEdit.from_list(Item, [])
        cb = lambda e: None
        grid.on_change(cb)
        assert cb in grid._change_handlers

    def test_on_change_non_callable_raises(self):
        grid = ModelGridInlineEdit.from_list(Item, [])
        with pytest.raises(TypeError):
            grid.on_change('not callable')  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# SqlModelAdapter
# ---------------------------------------------------------------------------

sqlmodel = pytest.importorskip('sqlmodel', reason='sqlmodel not installed')
SqlModelAdapter = pytest.importorskip('niceview.sqlmodel_adapter', reason='sqlmodel not installed').SqlModelAdapter


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


class DbItem(sqlmodel.SQLModel, table=True):
    __tablename__ = 'test_dbitems'
    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    name: str = ''
    value: int = 0
    updated_at: datetime.datetime = sqlmodel.Field(default_factory=_now)


class DbItemNoLock(sqlmodel.SQLModel, table=True):
    __tablename__ = 'test_dbitems_nolock'
    id: int | None = sqlmodel.Field(default=None, primary_key=True)
    name: str = ''


@pytest.fixture
def engine():
    eng = sqlmodel.create_engine('sqlite://', connect_args={'check_same_thread': False})
    sqlmodel.SQLModel.metadata.create_all(eng)
    yield eng
    sqlmodel.SQLModel.metadata.drop_all(eng)


@pytest.fixture
def populated_engine(engine):
    with sqlmodel.Session(engine) as session:
        session.add(DbItem(name='alpha', value=1))
        session.add(DbItem(name='beta', value=2))
        session.commit()
    return engine


class TestSqlModelAdapterInit:
    def test_valid_init(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        assert adapter._key_field == 'id'
        assert adapter._lock_field == 'updated_at'

    def test_non_sqlmodel_type_raises(self, engine):
        with pytest.raises(TypeError):
            SqlModelAdapter(pydantic.BaseModel, engine)  # type: ignore

    def test_non_type_raises(self, engine):
        with pytest.raises(TypeError):
            SqlModelAdapter(DbItem(), engine)  # type: ignore

    def test_missing_key_field_raises(self, engine):
        with pytest.raises(ValueError):
            SqlModelAdapter(DbItem, engine, key_field='nonexistent')

    def test_missing_lock_field_raises(self, engine):
        with pytest.raises(ValueError):
            SqlModelAdapter(DbItem, engine, lock_field='nonexistent')

    def test_lock_field_none_allowed(self, engine):
        adapter = SqlModelAdapter(DbItemNoLock, engine, lock_field=None)
        assert adapter._lock_field is None

    def test_empty_key_field_raises(self, engine):
        with pytest.raises(ValueError):
            SqlModelAdapter(DbItem, engine, key_field='')


class TestSqlModelAdapterCreate:
    def test_create_returns_item_with_id(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='new', value=42))
        assert item.id is not None

    def test_create_persists_to_db(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        adapter.create(DbItem(name='persisted', value=7))
        items = list(adapter)
        assert any(i.name == 'persisted' for i in items)

    def test_create_wrong_type_raises(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        with pytest.raises(TypeError):
            adapter.create(Item(name='wrong'))  # type: ignore

    def test_create_sets_lock_field(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        before = _now().replace(tzinfo=None)  # SQLite returns tz-naive datetimes
        item = adapter.create(DbItem(name='lock_test'))
        assert item.updated_at.replace(tzinfo=None) >= before


class TestSqlModelAdapterRead:
    def test_read_existing(self, populated_engine):
        adapter = SqlModelAdapter(DbItem, populated_engine)
        items = list(adapter)
        key = adapter.key_from_item(items[0])
        read_item = adapter.read(key)
        assert read_item.name == items[0].name

    def test_read_by_int_key(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        created = adapter.create(DbItem(name='r', value=5))
        fetched = adapter.read(created.id)
        assert fetched.name == 'r'

    def test_read_missing_raises(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        with pytest.raises(ValueError):
            adapter.read(9999)

    def test_read_returns_detached_object(self, populated_engine):
        adapter = SqlModelAdapter(DbItem, populated_engine)
        items = list(adapter)
        item = adapter.read(adapter.key_from_item(items[0]))
        assert isinstance(item, DbItem)


class TestSqlModelAdapterUpdate:
    def test_update_persists_change(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='old', value=1))
        key = adapter.key_from_item(item)
        item.name = 'new'
        adapter.update(item)
        assert adapter.read(key).name == 'new'

    def test_update_returns_new_instance(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='x'))
        item.name = 'y'
        result = adapter.update(item)
        assert result is not item

    def test_update_refreshes_lock_field(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='lock'))
        before = item.updated_at
        item.name = 'changed'
        result = adapter.update(item)
        assert result.updated_at >= before

    def test_update_optimistic_lock_conflict_raises(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='conflict'))
        item.name = 'v1'
        v1 = adapter.update(item)
        item.name = 'v2'
        with pytest.raises(ValueError, match='changed by another user'):
            adapter.update(item)  # stale lock field

    def test_update_conflict_raises_conflict_error(self, engine):
        # The conflict is a ConflictError (subclass of ValueError), so UI wrappers
        # can catch it specifically while old callers catching ValueError still work.
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='conflict2'))
        item.name = 'v1'
        adapter.update(item)
        item.name = 'v2'
        with pytest.raises(ConflictError):
            adapter.update(item)

    def test_update_missing_raises(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        ghost = DbItem(id=9999, name='ghost', updated_at=_now())
        with pytest.raises(ValueError):
            adapter.update(ghost)

    def test_update_missing_is_not_conflict(self, engine):
        # A deleted/missing row must report "not found", not an optimistic-lock conflict.
        adapter = SqlModelAdapter(DbItem, engine)
        ghost = DbItem(id=9999, name='ghost', updated_at=_now())
        with pytest.raises(ValueError, match='not found'):
            adapter.update(ghost)

    def test_update_no_lock_field(self, engine):
        adapter = SqlModelAdapter(DbItemNoLock, engine, lock_field=None)
        item = adapter.create(DbItemNoLock(name='nolockitem'))
        item.name = 'changed'
        result = adapter.update(item)
        assert result.name == 'changed'


class TestSqlModelAdapterDelete:
    def test_delete_removes_item(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='del'))
        key = adapter.key_from_item(item)
        adapter.delete(key)
        with pytest.raises(ValueError):
            adapter.read(key)

    def test_delete_missing_raises(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        with pytest.raises(ValueError):
            adapter.delete(9999)


class TestSqlModelAdapterIter:
    def test_iter_yields_all(self, populated_engine):
        adapter = SqlModelAdapter(DbItem, populated_engine)
        items = list(adapter)
        assert len(items) == 2
        assert {i.name for i in items} == {'alpha', 'beta'}

    def test_iter_empty(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        assert list(adapter) == []

    def test_query_all_strs(self, populated_engine):
        adapter = SqlModelAdapter(DbItem, populated_engine)
        pairs = list(adapter._query_all_strs())
        assert len(pairs) == 2
        for key, s in pairs:
            assert isinstance(key, str)
            assert isinstance(s, str)


class TestSqlModelAdapterKeys:
    def test_key_from_item_is_string(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='k'))
        assert isinstance(adapter.key_from_item(item), str)

    def test_key_from_item_no_pk_raises(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        with pytest.raises(ValueError):
            adapter.key_from_item(DbItem(name='no-pk'))  # id is None

    def test_key_from_item_wrong_type_raises(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        with pytest.raises(TypeError):
            adapter.key_from_item(Item(name='wrong'))  # type: ignore

class TestSqlModelAdapterReactive:
    def test_on_change_fires_on_create(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.create(DbItem(name='x'))
        assert called == [True]

    def test_on_change_fires_on_update(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='old'))
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        item.name = 'new'
        adapter.update(item)
        assert called == [True]

    def test_on_change_fires_on_delete(self, engine):
        adapter = SqlModelAdapter(DbItem, engine)
        item = adapter.create(DbItem(name='del'))
        key = adapter.key_from_item(item)
        called: list[bool] = []
        adapter.on_change(lambda: called.append(True))
        adapter.delete(key)
        assert called == [True]

    def test_isinstance_reactive_adapter(self, engine):
        from niceview.dataadapter import ReactiveAdapter
        adapter = SqlModelAdapter(DbItem, engine)
        assert isinstance(adapter, ReactiveAdapter)


# ---------------------------------------------------------------------------
# FilteredAdapter
# ---------------------------------------------------------------------------

class TestFilteredAdapterReload:
    def test_reload_forwards_to_inner_reloadable(self, tmp_path):
        from niceview.dataadapter import FilteredAdapter, JsonListAdapter, ReloadableAdapter
        path = tmp_path / 'items.json'
        inner = JsonListAdapter(Item, path)
        fa = FilteredAdapter(inner, predicate=lambda i: True)
        assert isinstance(fa, ReloadableAdapter)
        called: list[bool] = []
        inner.on_change(lambda: called.append(True))
        fa.reload()
        assert called == [True]

    def test_reload_noop_when_inner_not_reloadable(self):
        from niceview.dataadapter import FilteredAdapter
        inner = ListAdapter(Item, [Item(name='a')])
        fa = FilteredAdapter(inner, predicate=lambda i: True)
        fa.reload()  # should not raise


# ---------------------------------------------------------------------------
# items() — CollectionAdapter default + FilteredAdapter
# ---------------------------------------------------------------------------

class TestCollectionAdapterItems:
    def setup_method(self):
        self.items = [Item(name='a'), Item(name='b'), Item(name='c')]
        self.adapter = ListAdapter(Item, self.items)

    def test_items_yields_tuples(self):
        result = list(self.adapter.items())
        assert len(result) == 3
        for key, item in result:
            assert isinstance(key, str)
            assert isinstance(item, Item)

    def test_items_key_matches_key_from_item(self):
        for key, item in self.adapter.items():
            assert key == self.adapter.key_from_item(item)

    def test_items_all_items_present(self):
        names = [item.name for _, item in self.adapter.items()]
        assert names == ['a', 'b', 'c']

    def test_items_key_allows_read(self):
        for key, item in self.adapter.items():
            assert self.adapter.read(key) is item

    def test_items_empty_adapter(self):
        adapter = ListAdapter(Item, [])
        assert list(adapter.items()) == []

    def test_items_json_list_adapter(self, tmp_path):
        path = tmp_path / 'items.json'
        adapter = JsonListAdapter(Item, path)
        adapter.create(Item(name='x'))
        adapter.create(Item(name='y'))
        pairs = list(adapter.items())
        assert len(pairs) == 2
        names = [item.name for _, item in pairs]
        assert names == ['x', 'y']


class TestFilteredAdapterItems:
    def setup_method(self):
        self.items = [Item(name='a', value=1), Item(name='b', value=2), Item(name='c', value=1)]
        self.inner = ListAdapter(Item, self.items)
        self.filtered = __import__('niceview.dataadapter', fromlist=['FilteredAdapter']).FilteredAdapter(
            self.inner, predicate=lambda i: i.value == 1)

    def test_items_only_matching(self):
        pairs = list(self.filtered.items())
        assert len(pairs) == 2
        names = [item.name for _, item in pairs]
        assert set(names) == {'a', 'c'}

    def test_items_key_matches_inner(self):
        for key, item in self.filtered.items():
            assert key == self.inner.key_from_item(item)

    def test_items_key_readable_via_inner(self):
        for key, item in self.filtered.items():
            assert self.inner.read(key) is item
