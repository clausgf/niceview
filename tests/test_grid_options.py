"""Unit tests for the grid's choice-column derivation (refData / select editor).

These check the pure column builder, not the browser: aggrid's rendering of refData and the
select editor is covered separately (Playwright), out of the regular suite.
"""
from typing import Annotated, Literal

import pydantic

import niceview
from niceview.dataadapter import ListAdapter
from niceview.modelgrid import (ModelGrid, _collect_aggrid_cols, _field_options,
                                _number_value_formatter_js)


ROOM_LABELS = {'meeting': 'Meeting room', 'lab': 'Lab', 'other': 'Other'}


class Room(pydantic.BaseModel):
    name: str = ''
    kind: Annotated[
        Literal['meeting', 'lab', 'other'],
        niceview.Field(widget_type='ui.select', options=ROOM_LABELS),
    ] = 'meeting'
    plain: Literal['a', 'b'] = 'a'


class Author(pydantic.BaseModel):
    name: str = ''

    def __str__(self) -> str:
        return self.name


class BookRel(pydantic.BaseModel):
    """author is the related object (relationship-style)."""
    title: str = ''
    author: Annotated[Author | None, niceview.Field(widget_type='modelselect', item_type=Author)] = None


class BookFk(pydantic.BaseModel):
    """author is a scalar key (FK-style)."""
    title: str = ''
    author: Annotated[str, niceview.Field(widget_type='modelselect', item_type=Author)] = ''


def _cols(model, repositories=None):
    grid = ModelGrid.from_list(model, [])
    return {c['field']: c for c in _collect_aggrid_cols(grid._fields, repositories)}


class TestStaticAndLiteral:
    def test_dict_options_get_refdata_and_select(self):
        col = _cols(Room)['kind']
        assert col['refData'] == ROOM_LABELS
        assert col['cellEditor'] == 'agSelectCellEditor'
        assert col['cellEditorParams']['values'] == ['meeting', 'lab', 'other']

    def test_bare_literal_gets_select_without_refdata(self):
        col = _cols(Room)['plain']
        assert 'refData' not in col
        assert col['cellEditorParams']['values'] == ['a', 'b']

    def test_non_choice_field_untouched(self):
        col = _cols(Room)['name']
        assert 'refData' not in col and 'cellEditor' not in col


class TestModelselect:
    def _repo(self):
        authors = [Author(name='Alice'), Author(name='Bob')]
        return ListAdapter(Author, authors), authors

    def test_relationship_object_is_display_only(self):
        repo, authors = self._repo()
        col = _cols(BookRel, {Author: repo})['author']
        expected = {repo.key_from_item(a): a.name for a in authors}
        assert col['refData'] == expected
        assert 'cellEditor' not in col      # write-back needs the form's FK sync
        assert col['editable'] is False

    def test_scalar_fk_gets_select(self):
        repo, authors = self._repo()
        col = _cols(BookFk, {Author: repo})['author']
        expected_keys = [repo.key_from_item(a) for a in authors]
        assert col['refData'] == {repo.key_from_item(a): a.name for a in authors}
        assert col['cellEditor'] == 'agSelectCellEditor'
        assert col['cellEditorParams']['values'] == expected_keys

    def test_no_repository_leaves_field_plain(self):
        # Without a repository the modelselect column stays as-is (str() display, no refData).
        labels, values = _field_options('author', _cols_info(BookRel, 'author'), None)
        assert labels is None and values is None


def _cols_info(model, field_name):
    grid = ModelGrid.from_list(model, [])
    return grid._fields[field_name]


class Flags(pydantic.BaseModel):
    active: bool = True
    name: str = ''


class Prices(pydantic.BaseModel):
    plain: float = 0.0
    rounded: Annotated[float, niceview.Field(precision=2)] = 0.0
    formatted: Annotated[float, niceview.Field(number_format='%.2f')] = 0.0
    with_prefix_suffix: Annotated[float, niceview.Field(prefix='$', suffix=' USD')] = 0.0
    weird_format: Annotated[float, niceview.Field(number_format='%05d')] = 0.0


class TestBooleanColumn:
    def test_bool_field_gets_boolean_cell_data_type(self):
        col = _cols(Flags)['active']
        assert col['cellDataType'] == 'boolean'

    def test_bool_field_gets_no_forced_text_filter(self):
        col = _cols(Flags)['active']
        assert 'filter' not in col

    def test_non_bool_field_untouched(self):
        col = _cols(Flags)['name']
        assert 'cellDataType' not in col


class TestNumberValueFormatter:
    def test_plain_number_gets_no_formatter(self):
        col = _cols(Prices)['plain']
        assert ':valueFormatter' not in col

    def test_precision_becomes_a_fixed_formatter(self):
        col = _cols(Prices)['rounded']
        assert col[':valueFormatter'] == "(params) => params.value == null ? '' : '' + (params.value.toFixed(2)) + ''"

    def test_number_format_pattern_extracts_precision(self):
        col = _cols(Prices)['formatted']
        assert 'toFixed(2)' in col[':valueFormatter']

    def test_prefix_and_suffix_without_precision(self):
        col = _cols(Prices)['with_prefix_suffix']
        assert col[':valueFormatter'] == "(params) => params.value == null ? '' : '$' + (params.value) + ' USD'"

    def test_unrecognized_number_format_pattern_is_ignored(self):
        info = _cols_info(Prices, 'weird_format')
        assert _number_value_formatter_js(info) is None
