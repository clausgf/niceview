"""Tests for lenient JSON loading: lenient_model_load, lenient_list_load,
and the strict= parameter on JsonAdapter / JsonListAdapter."""
import json
import logging
import pytest
from pathlib import Path
from pydantic import BaseModel

from niceview.dataadapter import (
    JsonAdapter,
    JsonListAdapter,
    lenient_model_load,
    lenient_list_load,
)


class Simple(BaseModel):
    name: str = 'default'
    count: int = 0
    ratio: float = 1.0


class WithRequired(BaseModel):
    required_id: str
    label: str = 'ok'


# ---------------------------------------------------------------------------
# lenient_model_load
# ---------------------------------------------------------------------------

class TestLenientModelLoad:
    def test_valid_json_loads_normally(self):
        result = lenient_model_load(Simple, '{"name": "hello", "count": 3}')
        assert result.name == 'hello'
        assert result.count == 3
        assert result.ratio == 1.0

    def test_valid_json_no_log(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            lenient_model_load(Simple, '{"name": "hello"}')
        assert caplog.records == []

    def test_malformed_json_returns_default(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_model_load(Simple, 'not-json', context='myfile.json')
        assert result == Simple()
        assert caplog.records

    def test_malformed_json_logs_context(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            lenient_model_load(Simple, 'not-json', context='myfile.json')
        assert 'myfile.json' in caplog.text

    def test_json_array_returns_default(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_model_load(Simple, '[1, 2, 3]', context='f.json')
        assert result == Simple()
        assert caplog.records

    def test_unknown_field_ignored(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_model_load(Simple, '{"name": "x", "unknown_key": 99}')
        assert result.name == 'x'
        assert not hasattr(result, 'unknown_key')

    def test_unknown_field_logged(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            lenient_model_load(Simple, '{"name": "x", "ghost": 99}', context='f.json')
        assert 'ghost' in caplog.text

    def test_invalid_field_uses_default(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_model_load(Simple, '{"name": "hi", "count": "abc"}')
        assert result.count == 0

    def test_invalid_field_does_not_affect_neighbour(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_model_load(Simple, '{"name": "intact", "count": "bad"}')
        assert result.name == 'intact'
        assert result.count == 0

    def test_multiple_invalid_fields_all_use_default(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_model_load(Simple, '{"count": "abc", "ratio": "xyz"}')
        assert result.count == 0
        assert result.ratio == 1.0
        errors = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(errors) >= 2

    def test_empty_object_uses_all_defaults(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_model_load(Simple, '{}')
        assert result == Simple()
        assert caplog.records == []

    def test_required_field_present_loads_normally(self):
        result = lenient_model_load(WithRequired, '{"required_id": "abc"}')
        assert result.required_id == 'abc'
        assert result.label == 'ok'

    def test_required_field_missing_raises(self):
        with pytest.raises(Exception):
            lenient_model_load(WithRequired, '{"label": "hi"}')

    def test_context_appears_in_log(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            lenient_model_load(Simple, 'bad json', context='/path/to/data.json')
        assert '/path/to/data.json' in caplog.text


# ---------------------------------------------------------------------------
# lenient_list_load
# ---------------------------------------------------------------------------

class TestLenientListLoad:
    def test_valid_list_returns_all_items(self):
        result = lenient_list_load(Simple, '[{"name": "a"}, {"name": "b"}]')
        assert len(result) == 2
        assert result[0].name == 'a'
        assert result[1].name == 'b'

    def test_malformed_json_returns_empty(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_list_load(Simple, 'not-json', context='list.json')
        assert result == []
        assert caplog.records

    def test_json_object_returns_empty(self, caplog):
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_list_load(Simple, '{"x": 1}', context='list.json')
        assert result == []
        assert caplog.records

    def test_item_with_bad_field_survives_with_default(self, caplog):
        data = '[{"name": "ok"}, {"name": "also", "count": "bad"}]'
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_list_load(Simple, data)
        assert len(result) == 2
        assert result[1].count == 0

    def test_bad_item_does_not_affect_valid_neighbour(self, caplog):
        data = '[{"name": "ok"}, {"name": "also", "count": "bad"}]'
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_list_load(Simple, data)
        assert result[0].name == 'ok'

    def test_item_missing_required_field_is_skipped(self, caplog):
        data = '[{"required_id": "x"}, {"label": "no-id"}]'
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_list_load(WithRequired, data)
        assert len(result) == 1
        assert result[0].required_id == 'x'
        assert caplog.records

    def test_item_missing_required_field_logs_index(self, caplog):
        data = '[{"required_id": "x"}, {"label": "no-id"}]'
        with caplog.at_level(logging.ERROR, logger='niceview'):
            lenient_list_load(WithRequired, data, context='items.json')
        assert any('1' in r.message for r in caplog.records)

    def test_empty_list_returns_empty(self):
        result = lenient_list_load(Simple, '[]')
        assert result == []

    def test_unknown_fields_in_items_ignored_logged(self, caplog):
        data = '[{"name": "hi", "ghost": true}]'
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = lenient_list_load(Simple, data)
        assert len(result) == 1
        assert result[0].name == 'hi'
        assert 'ghost' in caplog.text


# ---------------------------------------------------------------------------
# JsonAdapter  strict=False (default)
# ---------------------------------------------------------------------------

class TestJsonAdapterLenient:
    def test_valid_file_loads(self, tmp_path: Path):
        p = tmp_path / 'item.json'
        p.write_text('{"name": "x", "count": 7}')
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False)
        assert adapter.read().name == 'x'
        assert adapter.read().count == 7

    def test_missing_file_returns_default(self, tmp_path: Path, caplog):
        p = tmp_path / 'missing.json'
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False)
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = adapter.read()
        assert result == Simple()
        assert caplog.records

    def test_malformed_file_returns_default(self, tmp_path: Path, caplog):
        p = tmp_path / 'bad.json'
        p.write_text('this is not json')
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False)
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = adapter.read()
        assert result == Simple()
        assert caplog.records

    def test_unknown_field_ignored_and_logged(self, tmp_path: Path, caplog):
        p = tmp_path / 'item.json'
        p.write_text('{"name": "hi", "unknown": 99}')
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False)
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = adapter.read()
        assert result.name == 'hi'
        assert caplog.records

    def test_bad_field_uses_default(self, tmp_path: Path, caplog):
        p = tmp_path / 'item.json'
        p.write_text('{"name": "ok", "count": "not-a-number"}')
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False)
        with caplog.at_level(logging.ERROR, logger='niceview'):
            result = adapter.read()
        assert result.name == 'ok'
        assert result.count == 0

    def test_save_read_roundtrip(self, tmp_path: Path):
        p = tmp_path / 'item.json'
        adapter = JsonAdapter(Simple, p, create_if_not_exist=True)
        adapter.save(Simple(name='roundtrip', count=42))
        result = adapter.read()
        assert result.name == 'roundtrip'
        assert result.count == 42

    def test_create_if_not_exist_writes_default_file(self, tmp_path: Path):
        p = tmp_path / 'new.json'
        JsonAdapter(Simple, p, create_if_not_exist=True)
        assert p.exists()
        data = json.loads(p.read_text())
        assert data['name'] == 'default'


# ---------------------------------------------------------------------------
# JsonAdapter  strict=True
# ---------------------------------------------------------------------------

class TestJsonAdapterStrict:
    def test_valid_file_loads(self, tmp_path: Path):
        p = tmp_path / 'item.json'
        p.write_text('{"name": "x", "count": 7}')
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False, strict=True)
        assert adapter.read().name == 'x'

    def test_malformed_file_raises(self, tmp_path: Path):
        p = tmp_path / 'bad.json'
        p.write_text('not json')
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False, strict=True)
        with pytest.raises(Exception):
            adapter.read()

    def test_bad_field_raises(self, tmp_path: Path):
        p = tmp_path / 'item.json'
        p.write_text('{"name": "ok", "count": "not-a-number"}')
        adapter = JsonAdapter(Simple, p, create_if_not_exist=False, strict=True)
        with pytest.raises(Exception):
            adapter.read()


# ---------------------------------------------------------------------------
# JsonListAdapter  strict=False (default)
# ---------------------------------------------------------------------------

class TestJsonListAdapterLenient:
    def test_valid_file_loads_all(self, tmp_path: Path):
        p = tmp_path / 'list.json'
        p.write_text('[{"name": "a"}, {"name": "b"}]')
        adapter = JsonListAdapter(Simple, p, create_if_not_exist=False)
        assert len(list(adapter)) == 2

    def test_malformed_file_returns_empty(self, tmp_path: Path, caplog):
        p = tmp_path / 'bad.json'
        p.write_text('not json at all')
        with caplog.at_level(logging.ERROR, logger='niceview'):
            adapter = JsonListAdapter(Simple, p, create_if_not_exist=False)
        assert list(adapter) == []
        assert caplog.records

    def test_bad_item_uses_defaults(self, tmp_path: Path, caplog):
        p = tmp_path / 'list.json'
        p.write_text('[{"name": "ok"}, {"name": "also", "count": "bad"}]')
        with caplog.at_level(logging.ERROR, logger='niceview'):
            adapter = JsonListAdapter(Simple, p, create_if_not_exist=False)
        items = list(adapter)
        assert len(items) == 2
        assert items[1].count == 0

    def test_create_if_not_exist_writes_empty_list(self, tmp_path: Path):
        p = tmp_path / 'new.json'
        JsonListAdapter(Simple, p, create_if_not_exist=True)
        assert p.exists()
        assert json.loads(p.read_text()) == []

    def test_reload_uses_lenient_loading(self, tmp_path: Path, caplog):
        p = tmp_path / 'list.json'
        p.write_text('[{"name": "a"}]')
        adapter = JsonListAdapter(Simple, p, create_if_not_exist=False)
        p.write_text('[{"name": "ok"}, {"count": "bad"}]')
        with caplog.at_level(logging.ERROR, logger='niceview'):
            adapter.reload()
        items = list(adapter)
        assert len(items) == 2
        assert items[1].count == 0
        assert caplog.records


# ---------------------------------------------------------------------------
# JsonListAdapter  strict=True
# ---------------------------------------------------------------------------

class TestJsonListAdapterStrict:
    def test_valid_file_loads(self, tmp_path: Path):
        p = tmp_path / 'list.json'
        p.write_text('[{"name": "a"}]')
        adapter = JsonListAdapter(Simple, p, create_if_not_exist=False, strict=True)
        assert len(list(adapter)) == 1

    def test_malformed_file_raises(self, tmp_path: Path):
        p = tmp_path / 'bad.json'
        p.write_text('not json')
        with pytest.raises(Exception):
            JsonListAdapter(Simple, p, create_if_not_exist=False, strict=True)

    def test_bad_item_raises(self, tmp_path: Path):
        p = tmp_path / 'list.json'
        p.write_text('[{"count": "not-a-number"}]')
        with pytest.raises(Exception):
            JsonListAdapter(Simple, p, create_if_not_exist=False, strict=True)
