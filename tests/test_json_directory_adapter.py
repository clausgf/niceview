"""Tests for JsonDirectoryAdapter — a CollectionAdapter over a directory of one-model-per-file
JSON documents, keyed by a model-owned field. Mirrors the CollectionAdapter contract the other
adapters are held to (CRUD, keys, listing, reactivity) plus the file-per-item specifics."""
import datetime
import logging

import pydantic
import pytest

from niceview import JsonDirectoryAdapter                 # must be exported at top level
from niceview.dataadapter import ConflictError, ReactiveAdapter, ReloadableAdapter


class Note(pydantic.BaseModel):
    id: str = ''
    title: str = ''
    updated_at: datetime.datetime | None = None

    def __str__(self) -> str:
        return self.title


@pytest.fixture
def adapter(tmp_path):
    return JsonDirectoryAdapter(Note, tmp_path, key_field='id')


def _write(dir_path, name, text):
    (dir_path / name).write_text(text, encoding='utf-8')


class TestConstruction:
    def test_rejects_non_directory(self, tmp_path):
        missing = tmp_path / 'nope'
        with pytest.raises(ValueError):
            JsonDirectoryAdapter(Note, missing, key_field='id')

    def test_rejects_unknown_key_field(self, tmp_path):
        with pytest.raises(ValueError):
            JsonDirectoryAdapter(Note, tmp_path, key_field='does_not_exist')


class TestCrud:
    def test_create_writes_a_file_named_by_key(self, adapter, tmp_path):
        adapter.create(Note(id='n1', title='First'))
        assert (tmp_path / 'n1.json').is_file()

    def test_create_read_roundtrip(self, adapter):
        adapter.create(Note(id='n1', title='First'))
        assert adapter.read('n1').title == 'First'

    def test_create_refuses_existing_key(self, adapter):
        adapter.create(Note(id='n1', title='First'))
        with pytest.raises(ValueError):
            adapter.create(Note(id='n1', title='Dupe'))

    def test_read_absent_key_raises(self, adapter):
        with pytest.raises(KeyError):
            adapter.read('ghost')

    def test_update_persists(self, adapter):
        adapter.create(Note(id='n1', title='First'))
        adapter.update(Note(id='n1', title='Edited'))
        assert adapter.read('n1').title == 'Edited'

    def test_update_absent_key_raises(self, adapter):
        with pytest.raises(KeyError):
            adapter.update(Note(id='ghost', title='x'))

    def test_delete_removes_file(self, adapter, tmp_path):
        adapter.create(Note(id='n1', title='First'))
        adapter.delete('n1')
        assert not (tmp_path / 'n1.json').exists()

    def test_delete_absent_key_raises(self, adapter):
        with pytest.raises(KeyError):
            adapter.delete('ghost')


class TestKeys:
    def test_key_from_item_reads_key_field(self, adapter):
        assert adapter.key_from_item(Note(id='abc', title='x')) == 'abc'

    @pytest.mark.parametrize('bad', ['../escape', 'a/b', '', '.', '..'])
    def test_path_traversal_keys_rejected(self, adapter, bad):
        with pytest.raises(ValueError):
            adapter.read(bad)


class TestListing:
    def test_iter_and_items(self, adapter):
        adapter.create(Note(id='a', title='Alice'))
        adapter.create(Note(id='b', title='Bob'))
        assert {n.id for n in adapter} == {'a', 'b'}
        assert dict(adapter.items()) .keys() == {'a', 'b'}

    def test_default_order_by_key(self, adapter):
        for k in ('c', 'a', 'b'):
            adapter.create(Note(id=k, title=k.upper()))
        assert [n.id for n in adapter] == ['a', 'b', 'c']

    def test_sort_key_orders_listing(self, tmp_path):
        ad = JsonDirectoryAdapter(Note, tmp_path, key_field='id', sort_key=lambda n: n.title)
        ad.create(Note(id='1', title='Zeta'))
        ad.create(Note(id='2', title='Alpha'))
        assert [n.title for n in ad] == ['Alpha', 'Zeta']

    def test_dotfiles_ignored(self, adapter, tmp_path):
        adapter.create(Note(id='a', title='Alice'))
        _write(tmp_path, '.hidden.json', '{"id":"h","title":"Hidden"}')
        assert [n.id for n in adapter] == ['a']

    def test_unusable_files_skipped_not_ghosted(self, adapter, tmp_path):
        # Lenient default: malformed JSON and a keyless file are skipped (would otherwise become
        # empty ghost records with key ''), while a valid object with one bad field is recovered.
        adapter.create(Note(id='a', title='Alice'))
        _write(tmp_path, 'bad.json', '{ not valid json')            # malformed -> skip
        _write(tmp_path, 'nokey.json', '{"title":"NoId"}')          # empty key -> skip
        _write(tmp_path, 'recover.json', '{"id":"c","title":5}')    # bad field -> lenient recover
        logging.disable(logging.CRITICAL)
        try:
            items = {n.id: n for n in adapter}
        finally:
            logging.disable(logging.NOTSET)
        assert set(items) == {'a', 'c'}      # bad + nokey skipped, recover kept
        assert items['c'].title == ''        # the invalid field was dropped, not ghosted


class TestStrict:
    def test_strict_skips_recoverable_files(self, tmp_path):
        ad = JsonDirectoryAdapter(Note, tmp_path, key_field='id', strict=True)
        ad.create(Note(id='a', title='Alice'))
        _write(tmp_path, 'recover.json', '{"id":"c","title":5}')    # strict -> reject -> skip
        logging.disable(logging.CRITICAL)
        try:
            keys = [n.id for n in ad]
        finally:
            logging.disable(logging.NOTSET)
        assert keys == ['a']

    def test_strict_read_raises_on_bad_file(self, tmp_path):
        ad = JsonDirectoryAdapter(Note, tmp_path, key_field='id', strict=True)
        _write(tmp_path, 'c.json', '{"id":"c","title":5}')
        with pytest.raises(Exception):
            ad.read('c')

    def test_lenient_read_recovers(self, tmp_path):
        ad = JsonDirectoryAdapter(Note, tmp_path, key_field='id')  # strict=False
        _write(tmp_path, 'c.json', '{"id":"c","title":5}')
        assert ad.read('c').id == 'c'


class TestReloadable:
    def test_is_reloadable_adapter(self, adapter):
        assert isinstance(adapter, ReloadableAdapter)

    def test_reload_notifies(self, adapter):
        calls = []
        adapter.on_change(lambda: calls.append(1))
        adapter.reload()
        assert calls == [1]


class TestReactive:
    def test_is_reactive_adapter(self, adapter):
        assert isinstance(adapter, ReactiveAdapter)

    def test_on_change_fires_on_mutations(self, adapter):
        calls = []
        adapter.on_change(lambda: calls.append(1))
        adapter.create(Note(id='a', title='A'))
        adapter.update(Note(id='a', title='B'))
        adapter.delete('a')
        assert len(calls) == 3


class TestOptimisticLocking:
    def test_stale_lock_raises_conflict(self, tmp_path):
        ad = JsonDirectoryAdapter(Note, tmp_path, key_field='id', lock_field='updated_at')
        ad.create(Note(id='n1', title='First'))
        stored = ad.read('n1')                       # has a fresh updated_at
        ad.update(Note(id='n1', title='Second', updated_at=stored.updated_at))  # ok
        with pytest.raises(ConflictError):
            ad.update(Note(id='n1', title='Third', updated_at=stored.updated_at))  # stale token
