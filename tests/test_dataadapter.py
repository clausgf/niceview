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
        assert self.adapter.read(0).name == 'a'

    def test_read_last(self):
        assert self.adapter.read(2).name == 'c'

    def test_read_by_string_key(self):
        assert self.adapter.read('1').name == 'b'

    def test_read_out_of_bounds_raises(self):
        with pytest.raises(IndexError):
            self.adapter.read(99)

    def test_read_negative_index_raises(self):
        with pytest.raises(IndexError):
            self.adapter.read(-1)


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


class TestListModelAdapterUpdate:
    def setup_method(self):
        self.items = [Item(name='a', value=1), Item(name='b', value=2)]
        self.adapter = ListModelAdapter(Item, self.items)

    def test_update_replaces_item(self):
        updated = Item(name='X', value=99)
        self.adapter.update(updated, '0')
        assert self.items[0].name == 'X'

    def test_update_returns_item(self):
        updated = Item(name='X')
        result = self.adapter.update(updated, '0')
        assert result is updated

    def test_update_out_of_bounds_raises(self):
        with pytest.raises(IndexError):
            self.adapter.update(Item(), '99')


class TestListModelAdapterDelete:
    def setup_method(self):
        self.items = [Item(name='a'), Item(name='b'), Item(name='c')]
        self.adapter = ListModelAdapter(Item, self.items)

    def test_delete_removes_item(self):
        self.adapter.delete('1')
        assert len(self.items) == 2
        assert self.items[0].name == 'a'
        assert self.items[1].name == 'c'

    def test_delete_out_of_bounds_raises(self):
        with pytest.raises(IndexError):
            self.adapter.delete('99')


class TestListModelAdapterKeys:
    def setup_method(self):
        self.items = [Item(name='a'), Item(name='b')]
        self.adapter = ListModelAdapter(Item, self.items)

    def test_key_from_str_int(self):
        assert self.adapter.key_from_str('2') == 2

    def test_key_from_str_already_int(self):
        assert self.adapter.key_from_str(0) == 0

    def test_iter_yields_all_items(self):
        result = list(self.adapter)
        assert len(result) == 2
        assert result[0].name == 'a'

    def test_query_all_strs(self):
        pairs = list(self.adapter.query_all_strs())
        assert pairs == [('0', 'a'), ('1', 'b')]


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
