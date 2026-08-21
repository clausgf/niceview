"""Key-select modelselect: a scalar field that stores a foreign key into a CollectionAdapter,
shows the collection's labels, and edits through a searchable select.

End-to-end write-back is covered in the browser (Playwright); here we check the pure resolution:
mode detection, field-name repositories, item_type inference, options, and the existence validator.
"""
from typing import Annotated

import pydantic

import niceview
from niceview.dataadapter import ListAdapter
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid, _collect_aggrid_cols, _field_options
from niceview.fields import Fields
from niceview.util import field_stores_model, resolve_repository


class Building(pydantic.BaseModel):
    name: str = ''

    def __str__(self) -> str:
        return self.name


class Room(pydantic.BaseModel):
    name: str = ''
    building: Annotated[
        str | None, niceview.Field(widget_type='modelselect', item_type=Building)
    ] = None


class RoomNoItemType(pydantic.BaseModel):
    name: str = ''
    building: Annotated[str | None, niceview.Field(widget_type='modelselect')] = None


def _buildings():
    items = [Building(name='Main'), Building(name='Annex')]
    return ListAdapter(Building, items), items


class TestModeDetection:
    def test_scalar_key_field_is_key_select(self):
        fi = Fields(Room)['building']
        assert fi.widget_type == 'modelselect'
        assert field_stores_model(fi) is False       # str field -> key-select

    def test_repository_lookup_prefers_field_name(self):
        by_name = {'building': 'NAME'}
        by_type = {Building: 'TYPE'}
        assert resolve_repository(by_name, 'building', Building) == 'NAME'
        assert resolve_repository(by_type, 'building', Building) == 'TYPE'
        assert resolve_repository({'building': 'NAME', Building: 'TYPE'}, 'building', Building) == 'NAME'
        assert resolve_repository({}, 'building', Building) is None


class TestPrepareModelselect:
    def _form(self, model, repo_key):
        repo, items = _buildings()
        form = ModelForm.from_item(model())
        form.with_repositories({repo_key: repo})
        fi = form._fields['building']
        form._prepare_modelselect('building', fi)
        return fi, repo, items

    def test_options_labels_and_searchable(self):
        fi, repo, items = self._form(Room, 'building')          # field-name repo
        assert fi.options == {repo.key_from_item(b): b.name for b in items}
        assert fi.with_input is True

    def test_item_type_inferred_from_adapter(self):
        fi, repo, items = self._form(RoomNoItemType, 'building')  # no item_type on the field
        assert fi.item_type is Building

    def test_type_keyed_repository_still_works(self):
        fi, repo, items = self._form(Room, Building)             # legacy type key
        assert fi.options == {repo.key_from_item(b): b.name for b in items}

    def test_existence_validator(self):
        fi, repo, items = self._form(Room, 'building')
        valid_key = repo.key_from_item(items[0])
        (msg, check), = fi.validation.items()
        assert check(valid_key) is True
        assert check(None) is True
        assert check('does-not-exist') is False


class TestGridKeySelect:
    def test_scalar_key_column_gets_refdata_and_select(self):
        repo, items = _buildings()
        grid = ModelGrid.from_list(Room, [])
        cols = {c['field']: c for c in _collect_aggrid_cols(grid._fields, {'building': repo})}
        col = cols['building']
        assert col['refData'] == {repo.key_from_item(b): b.name for b in items}
        assert col['cellEditor'] == 'agSelectCellEditor'
        assert col['cellEditorParams']['values'] == [repo.key_from_item(b) for b in items]

    def test_field_name_and_type_key_equivalent(self):
        repo, items = _buildings()
        fi = Fields(Room)['building']
        by_name = _field_options('building', fi, {'building': repo})
        by_type = _field_options('building', fi, {Building: repo})
        assert by_name == by_type
