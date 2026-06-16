import json
import pytest
import pydantic
from pathlib import Path

from niceview.dataadapter import ListModelAdapter, JsonSingleModelAdapter


class Item(pydantic.BaseModel):
    name: str = ''
    value: int = 0

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# ListModelAdapter
# ---------------------------------------------------------------------------

class TestListModelAdapterRead:
    def setup_method(self):
        self.items = [Item(name='a', value=1), Item(name='b', value=2), Item(name='c', value=3)]
        self.adapter = ListModelAdapter(Item, self.items)

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


class TestListModelAdapterCreate:
    def setup_method(self):
        self.items = [Item(name='a')]
        self.adapter = ListModelAdapter(Item, self.items)

    def test_create_appends_item(self):
        new_item = Item(name='z', value=99)
        self.adapter.create(new_item)
        assert len(self.items) == 2
        assert self.items[-1].name == 'z'

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


class TestListModelAdapterUpdate:
    def setup_method(self):
        self.items = [Item(name='a', value=1), Item(name='b', value=2)]
        self.adapter = ListModelAdapter(Item, self.items)

    def test_update_replaces_item(self):
        key = self.adapter.key_from_item(self.items[0])
        updated = Item(name='X', value=99)
        self.adapter.update(updated, key)
        assert self.items[0].name == 'X'

    def test_update_returns_item(self):
        key = self.adapter.key_from_item(self.items[0])
        updated = Item(name='X')
        result = self.adapter.update(updated, key)
        assert result is updated

    def test_update_unknown_key_raises(self):
        with pytest.raises(KeyError):
            self.adapter.update(Item(), 'not-a-valid-key')

    def test_update_same_object_inplace(self):
        key = self.adapter.key_from_item(self.items[0])
        self.items[0].name = 'modified'
        result = self.adapter.update(self.items[0], key)
        assert result.name == 'modified'


class TestListModelAdapterDelete:
    def setup_method(self):
        self.items = [Item(name='a'), Item(name='b'), Item(name='c')]
        self.adapter = ListModelAdapter(Item, self.items)

    def test_delete_removes_item(self):
        key = self.adapter.key_from_item(self.items[1])
        self.adapter.delete(key)
        assert len(self.items) == 2
        assert self.items[0].name == 'a'
        assert self.items[1].name == 'c'

    def test_delete_unknown_key_raises(self):
        with pytest.raises(KeyError):
            self.adapter.delete('not-a-valid-key')

    def test_key_stable_after_delete(self):
        # key of 'c' (originally at index 2) stays valid after deleting 'b' (index 1)
        key_c = self.adapter.key_from_item(self.items[2])
        self.adapter.delete(self.adapter.key_from_item(self.items[1]))
        assert self.adapter.read(key_c).name == 'c'


class TestListModelAdapterKeys:
    def setup_method(self):
        self.items = [Item(name='a'), Item(name='b')]
        self.adapter = ListModelAdapter(Item, self.items)

    def test_key_from_item_is_string(self):
        key = self.adapter.key_from_item(self.items[0])
        assert isinstance(key, str)

    def test_key_from_item_unique_per_object(self):
        key_a = self.adapter.key_from_item(self.items[0])
        key_b = self.adapter.key_from_item(self.items[1])
        assert key_a != key_b

    def test_key_from_str_returns_string(self):
        assert self.adapter.key_from_str('12345') == '12345'

    def test_key_from_str_int_becomes_string(self):
        assert self.adapter.key_from_str(42) == '42'

    def test_iter_yields_all_items(self):
        result = list(self.adapter)
        assert len(result) == 2
        assert result[0].name == 'a'

    def test_query_all_strs_returns_valid_keys(self):
        pairs = list(self.adapter.query_all_strs())
        assert len(pairs) == 2
        for key, _ in pairs:
            assert self.adapter.read(key) is not None

    def test_query_all_strs_str_is_item_str(self):
        pairs = list(self.adapter.query_all_strs())
        names = [s for _, s in pairs]
        assert names == ['a', 'b']


# ---------------------------------------------------------------------------
# JsonSingleModelAdapter
# ---------------------------------------------------------------------------

class TestJsonSingleModelAdapter:
    def test_create_if_not_exist(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonSingleModelAdapter(Item, path, create_if_not_exist=True)
        assert path.exists()

    def test_created_file_has_default_values(self, tmp_path):
        path = tmp_path / 'data.json'
        JsonSingleModelAdapter(Item, path, create_if_not_exist=True)
        data = json.loads(path.read_text())
        assert data == {'name': '', 'value': 0}

    def test_no_create_if_not_exist_does_not_create_file(self, tmp_path):
        path = tmp_path / 'data.json'
        JsonSingleModelAdapter(Item, path, create_if_not_exist=False)
        assert not path.exists()

    def test_read_existing_file(self, tmp_path):
        path = tmp_path / 'data.json'
        path.write_text(json.dumps({'name': 'hello', 'value': 42}))
        adapter = JsonSingleModelAdapter(Item, path, create_if_not_exist=False)
        item = adapter.read(0)
        assert item.name == 'hello'
        assert item.value == 42

    def test_update_writes_to_file(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonSingleModelAdapter(Item, path, create_if_not_exist=True)
        adapter.update(Item(name='updated', value=7), '0')
        data = json.loads(path.read_text())
        assert data['name'] == 'updated'
        assert data['value'] == 7

    def test_update_returns_persisted_item(self, tmp_path):
        path = tmp_path / 'data.json'
        adapter = JsonSingleModelAdapter(Item, path, create_if_not_exist=True)
        result = adapter.update(Item(name='x', value=3), '0')
        assert result.name == 'x'

    def test_path_is_directory_raises(self, tmp_path):
        with pytest.raises(ValueError):
            JsonSingleModelAdapter(Item, tmp_path, create_if_not_exist=False)

    def test_invalid_item_type_raises(self, tmp_path):
        path = tmp_path / 'data.json'
        with pytest.raises((ValueError, TypeError)):
            JsonSingleModelAdapter(str, path)  # type: ignore
