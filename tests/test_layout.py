"""
Unit tests for the form layout notation: parsing, validation, and how it feeds Fields.

Rendering is covered in test_acceptance_layout.py.
"""
import pydantic
import pytest

import niceview
from niceview.fields import Fields, LayoutField, LayoutGroup, layout_field_names, parse_layout

NAMES = {'a', 'b', 'c', 'd'}


class Model(pydantic.BaseModel):
    a: str = ''
    b: str = ''
    c: str = ''
    d: str = ''

    class Meta:
        profiles = {
            'flat': ['a', 'b'],
            'arranged': ['a', ['b', 'c']],
        }


class TestParsing:
    def test_flat_list_is_a_layout_without_rows(self):
        group = parse_layout(['a', 'b'], NAMES)
        assert group == LayoutGroup((LayoutField('a'), LayoutField('b')))

    def test_nesting_alternates_row_and_column(self):
        group = parse_layout(['a', ['b', ['c', 'd']]], NAMES)
        row = group.children[1]
        assert isinstance(row, LayoutGroup) and row.row is True
        column = row.children[1]
        assert isinstance(column, LayoutGroup) and column.row is False

    def test_field_classes_after_the_first_colon(self):
        # Tailwind's own prefixes contain colons, so only the first one separates.
        group = parse_layout(['a:sm:w-2/3 grow'], NAMES)
        assert group.children[0] == LayoutField('a', 'sm:w-2/3 grow')

    def test_title_makes_a_group(self):
        group = parse_layout(['# Address', 'a', 'b'], NAMES)
        assert group.title == 'Address'
        assert group.card is True
        assert layout_field_names(group) == ['a', 'b']

    def test_second_level_title_is_a_section_without_a_card(self):
        group = parse_layout(['## Address', 'a', 'b'], NAMES)
        assert (group.title, group.card) == ('Address', False)
        assert layout_field_names(group) == ['a', 'b']

    def test_a_section_without_a_card_is_a_column_too(self):
        # Same rule as the card: the heading sits above its fields, wherever the group sits.
        group = parse_layout(['a', ['## Section', 'b', 'c']], NAMES)
        section = group.children[1]
        assert isinstance(section, LayoutGroup) and section.row is False

    def test_container_classes(self):
        assert parse_layout([':gap-8 items-end', 'a'], NAMES).classes == 'gap-8 items-end'

    def test_title_and_classes_together(self):
        group = parse_layout(['# Address', ':gap-8', 'a'], NAMES)
        assert (group.title, group.classes) == ('Address', 'gap-8')

    def test_classes_of_a_section_without_a_card(self):
        group = parse_layout(['## Address', ':gap-8', 'a'], NAMES)
        assert (group.title, group.card, group.classes) == ('Address', False, 'gap-8')

    def test_titled_group_is_always_a_column(self):
        # A section reads the same wherever it sits, so it does not follow the alternation.
        group = parse_layout(['a', ['# Section', 'b', 'c']], NAMES)
        section = group.children[1]
        assert isinstance(section, LayoutGroup) and section.row is False

    def test_children_of_a_titled_group_are_rows_again(self):
        group = parse_layout([['# Section', ['a', 'b']]], NAMES)
        section = group.children[0]
        assert isinstance(section, LayoutGroup)
        inner = section.children[0]
        assert isinstance(inner, LayoutGroup) and inner.row is True

    def test_field_names_in_render_order(self):
        assert layout_field_names(parse_layout(['a', ['b', ['c']], 'd'], NAMES)) == ['a', 'b', 'c', 'd']


class TestParsingErrors:
    def test_unknown_field_names_its_position(self):
        with pytest.raises(ValueError, match=r"layout\[1\]\[0\]: unknown field 'nope'"):
            parse_layout(['a', ['nope']], NAMES)

    def test_metadata_must_come_first(self):
        with pytest.raises(ValueError, match='must come before the fields'):
            parse_layout(['a', ':gap-8'], NAMES)

    def test_two_titles(self):
        with pytest.raises(ValueError, match='already has a title'):
            parse_layout(['# One', '# Two', 'a'], NAMES)

    def test_empty_title(self):
        with pytest.raises(ValueError, match='needs a title'):
            parse_layout(['#', 'a'], NAMES)

    def test_empty_title_without_a_card(self):
        with pytest.raises(ValueError, match='needs a title'):
            parse_layout(['##', 'a'], NAMES)

    def test_two_titles_of_different_levels(self):
        with pytest.raises(ValueError, match='already has a title'):
            parse_layout(['# One', '## Two', 'a'], NAMES)

    def test_deeper_heading_levels(self):
        with pytest.raises(ValueError, match='not a heading level'):
            parse_layout(['### Address', 'a'], NAMES)

    def test_empty_classes(self):
        with pytest.raises(ValueError, match='needs at least one CSS class'):
            parse_layout([':', 'a'], NAMES)

    def test_empty_group(self):
        with pytest.raises(ValueError, match='at least one field'):
            parse_layout(['a', []], NAMES)

    def test_wrong_element_type(self):
        with pytest.raises(ValueError, match='expected a field name or a nested list'):
            parse_layout(['a', 42], NAMES)

    def test_not_a_list(self):
        with pytest.raises(ValueError, match='expected a list'):
            parse_layout('a', NAMES)


class TestFieldsIntegration:
    def test_layout_defines_the_field_set_and_order(self):
        fields = Fields(Model, layout=['c', ['a', 'b']])
        assert list(fields.field_names) == ['c', 'a', 'b']
        assert 'd' not in fields

    def test_flat_profile_still_works(self):
        fields = Fields(Model, profile='flat')
        assert list(fields.field_names) == ['a', 'b']
        assert fields.layout == LayoutGroup((LayoutField('a'), LayoutField('b')))

    def test_profile_may_be_nested(self):
        fields = Fields(Model, profile='arranged')
        assert list(fields.field_names) == ['a', 'b', 'c']
        assert fields.layout.children[1].row is True

    def test_layout_kwarg_wins_over_profile(self):
        fields = Fields(Model, profile='flat', layout=['d'])
        assert list(fields.field_names) == ['d']

    def test_default_layout_is_flat(self):
        fields = Fields(Model)
        assert fields.layout.children == tuple(LayoutField(n) for n in ['a', 'b', 'c', 'd'])
        assert fields.layout.row is False

    def test_duplicate_field(self):
        with pytest.raises(ValueError, match='more than once'):
            Fields(Model, layout=['a', ['a', 'b']])

    def test_excluded_field_in_layout(self):
        with pytest.raises(ValueError, match='not available'):
            Fields(Model, exclude='b', layout=['a', 'b'])

    def test_unknown_field_in_layout(self):
        with pytest.raises(ValueError, match="unknown field 'zzz'"):
            Fields(Model, layout=['a', 'zzz'])

    def test_field_infos_still_resolve(self):
        fields = Fields(Model, layout=[['a:w-1/2', 'b']])
        assert fields['a'].widget_type == 'ui.input'
        assert fields.layout.children[0].children[0].classes == 'w-1/2'

    def test_grid_style_consumers_see_a_flat_list(self):
        # ModelGrid/ModelList iterate field_names and ignore the tree.
        fields = Fields(Model, layout=['a', ['# Section', 'b', 'c']])
        assert list(fields) == ['a', 'b', 'c']


class TestFieldOrderInteraction:
    def test_field_order_applies_without_a_layout(self):
        class Ordered(pydantic.BaseModel):
            a: str = ''
            b: str = ''

            class Meta:
                field_order = ['b', 'a']

        assert list(Fields(Ordered).field_names) == ['b', 'a']

    def test_layout_defines_the_order_instead(self):
        class Ordered(pydantic.BaseModel):
            a: str = ''
            b: str = ''

            class Meta:
                field_order = ['b', 'a']

        assert list(Fields(Ordered, layout=['a', 'b']).field_names) == ['a', 'b']


class TestHiddenFields:
    def test_hidden_field_may_be_named_in_a_layout(self):
        from typing import Annotated

        class WithHidden(pydantic.BaseModel):
            a: str = ''
            secret: Annotated[str, niceview.Field(hidden=True)] = ''

        fields = Fields(WithHidden, layout=['a', 'secret'])
        assert list(fields.field_names) == ['a', 'secret']   # skipped at render time


class TestIncludeIsALayout:
    """An explicit field list orders the fields, however it was written."""

    def test_list_include_defines_the_order(self):
        assert list(Fields(Model, include=['c', 'a']).field_names) == ['c', 'a']

    def test_string_include_defines_the_order_too(self):
        assert list(Fields(Model, include='c, a').field_names) == ['c', 'a']

    def test_all_keeps_model_order(self):
        assert list(Fields(Model, include='__all__').field_names) == ['a', 'b', 'c', 'd']

    def test_duplicate_include(self):
        with pytest.raises(ValueError, match='more than once'):
            Fields(Model, include=['a', 'a'])
