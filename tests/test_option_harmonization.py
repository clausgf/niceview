"""Harmonization of options across components:
- Meta.include / Meta.exclude / Meta.field_infos are honoured by ModelGrid and ModelList (as
  they already were by ModelForm), overridable by the kwarg.
- Meta.default_profile picks a profile when no profile=/layout= kwarg is given, honoured
  wherever Fields() is built (ModelForm, ModelGrid, ModelList alike).
- DrillDownWrapper accepts title_field / subtitle_fields as aliases of item_title_field /
  item_subtitle_fields (the names ModelList uses), easing a ModelList <-> DrillDown switch.
"""
import pydantic

from niceview.fieldinfo import FieldInfo
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid
from niceview.modellist import ModelList
from niceview.drilldown import DrillDownWrapper


class IncludeMeta(pydantic.BaseModel):
    a: str = ''
    b: str = ''
    c: str = ''

    class Meta:
        include = ['a', 'b']


class ExcludeMeta(pydantic.BaseModel):
    a: str = ''
    b: str = ''
    secret: str = ''

    class Meta:
        exclude = ['secret']


class FieldInfosMeta(pydantic.BaseModel):
    a: str = ''
    secret: str = ''

    class Meta:
        field_infos = {'secret': FieldInfo(hidden=True)}


class DefaultProfileMeta(pydantic.BaseModel):
    a: str = ''
    b: str = ''
    c: str = ''

    class Meta:
        profiles = {'flat': ['a', 'b']}
        default_profile = 'flat'


class Person(pydantic.BaseModel):
    name: str = ''
    email: str = ''
    phone: str = ''


class TestMetaIncludeExclude:
    def test_form_honours_meta_include(self):
        assert list(ModelForm.from_item(IncludeMeta())._fields) == ['a', 'b']

    def test_grid_honours_meta_include(self):
        assert list(ModelGrid.from_list(IncludeMeta, [])._fields) == ['a', 'b']

    def test_list_honours_meta_include(self):
        assert list(ModelList.from_list(IncludeMeta, [])._fields) == ['a', 'b']

    def test_grid_honours_meta_exclude(self):
        assert 'secret' not in list(ModelGrid.from_list(ExcludeMeta, [])._fields)

    def test_list_honours_meta_exclude(self):
        assert 'secret' not in list(ModelList.from_list(ExcludeMeta, [])._fields)

    def test_kwarg_overrides_meta_include(self):
        assert list(ModelGrid.from_list(IncludeMeta, [], include=['c'])._fields) == ['c']

    def test_grid_honours_meta_field_infos(self):
        assert ModelGrid.from_list(FieldInfosMeta, [])._fields['secret'].hidden is True

    def test_list_honours_meta_field_infos(self):
        assert ModelList.from_list(FieldInfosMeta, [])._fields['secret'].hidden is True

    def test_kwarg_overrides_meta_field_infos(self):
        grid = ModelGrid.from_list(FieldInfosMeta, [], field_infos={'secret': FieldInfo(hidden=False)})
        assert grid._fields['secret'].hidden is False


class TestMetaDefaultProfile:
    def test_form_honours_default_profile(self):
        assert list(ModelForm.from_item(DefaultProfileMeta())._fields) == ['a', 'b']

    def test_grid_honours_default_profile(self):
        assert list(ModelGrid.from_list(DefaultProfileMeta, [])._fields) == ['a', 'b']

    def test_list_honours_default_profile(self):
        assert list(ModelList.from_list(DefaultProfileMeta, [])._fields) == ['a', 'b']

    def test_profile_kwarg_overrides_default_profile(self):
        assert list(ModelGrid.from_list(DefaultProfileMeta, [], include=['c'])._fields) == ['c']


class TestDrillDownFieldAliases:
    def test_title_field_alias(self):
        dd = DrillDownWrapper.from_list(Person, [], title_field='email')
        assert dd._item_title_field == 'email'

    def test_subtitle_fields_alias(self):
        dd = DrillDownWrapper.from_list(Person, [], subtitle_fields=['phone'])
        assert dd._item_subtitle_fields == ['phone']

    def test_item_form_wins_over_alias(self):
        dd = DrillDownWrapper.from_list(Person, [], item_title_field='name', title_field='email')
        assert dd._item_title_field == 'name'

    def test_canonical_names_still_work(self):
        dd = DrillDownWrapper.from_list(Person, [], item_title_field='email',
                                        item_subtitle_fields=['phone'])
        assert dd._item_title_field == 'email'
        assert dd._item_subtitle_fields == ['phone']
