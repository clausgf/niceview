"""
Unit tests for the model-free value conversions behind render_field():
to_widget_value() (Python value -> widget) and field_value() (widget -> Python value).

Rendering itself needs a NiceGUI context and is covered in test_acceptance_render_field.py.
"""
import datetime
from typing import Optional
from unittest.mock import MagicMock

import pytest

import niceview
import niceview.widgets
from niceview import Field, field_value, render_field, to_widget_value


def _widget(value):
    """A stand-in for a rendered widget: everything reads .value."""
    return MagicMock(value=value)


# ---------------------------------------------------------------------------
# to_widget_value — Python value -> widget value
# ---------------------------------------------------------------------------

class TestToWidgetValue:
    def test_plain_value_unchanged(self):
        assert to_widget_value(Field(widget_type='ui.input'), 'Alice') == 'Alice'

    def test_date_becomes_iso_string(self):
        fi = Field(widget_type='date')
        assert to_widget_value(fi, datetime.date(2026, 8, 5)) == '2026-08-05'

    def test_date_none_becomes_empty_string(self):
        assert to_widget_value(Field(widget_type='date'), None) == ''

    def test_date_string_passes_through(self):
        # JSON-sourced data is already an ISO string — no pre-conversion needed.
        assert to_widget_value(Field(widget_type='date'), '2026-08-05') == '2026-08-05'

    def test_time_drops_microseconds(self):
        fi = Field(widget_type='time')
        assert to_widget_value(fi, datetime.time(14, 30, 15, 123456)) == '14:30:15'

    def test_datetime_converted_to_local_tz(self):
        fi = Field(widget_type='datetime')
        value = datetime.datetime(2026, 8, 5, 12, 0, 0, tzinfo=datetime.timezone.utc)
        assert to_widget_value(fi, value, local_tz='Europe/Berlin') == '2026-08-05T14:00:00'

    def test_datetime_string_passes_through(self):
        fi = Field(widget_type='datetime')
        assert to_widget_value(fi, '2026-08-05T14:00:00') == '2026-08-05T14:00:00'

    def test_timedelta_becomes_iso_duration(self):
        fi = Field(widget_type='timedelta')
        assert to_widget_value(fi, datetime.timedelta(hours=1, minutes=30)) == 'PT1H30M'

    def test_multiselect_none_becomes_empty_list(self):
        fi = Field(widget_type='ui.select', multiple=True, options=['a', 'b'])
        assert to_widget_value(fi, None) == []

    def test_checkbox_group_none_becomes_empty_list(self):
        fi = Field(widget_type='checkbox_group', options=['a', 'b'])
        assert to_widget_value(fi, None) == []


# ---------------------------------------------------------------------------
# field_value — widget value -> Python value
# ---------------------------------------------------------------------------

class TestFieldValue:
    def test_input_returns_string(self):
        assert field_value(_widget('Alice'), Field(widget_type='ui.input')) == 'Alice'

    def test_number_defaults_to_float(self):
        value = field_value(_widget(5), Field(widget_type='ui.number'))
        assert value == 5.0
        assert type(value) is float

    def test_number_with_int_field_type_returns_int(self):
        value = field_value(_widget(5.0), Field(widget_type='ui.number', field_type=int))
        assert value == 5
        assert type(value) is int

    def test_cleared_number_returns_none(self):
        assert field_value(_widget(''), Field(widget_type='ui.number')) is None
        assert field_value(_widget(None), Field(widget_type='ui.number')) is None

    def test_switch_returns_bool(self):
        assert field_value(_widget(True), Field(widget_type='ui.switch')) is True

    def test_date_parsed(self):
        assert field_value(_widget('2026-08-05'), Field(widget_type='date')) == datetime.date(2026, 8, 5)

    def test_empty_date_returns_none(self):
        assert field_value(_widget(''), Field(widget_type='date')) is None

    def test_time_parsed(self):
        assert field_value(_widget('14:30:00'), Field(widget_type='time')) == datetime.time(14, 30)

    def test_datetime_parsed_from_local_tz_to_utc(self):
        value = field_value(_widget('2026-08-05T14:00:00'), Field(widget_type='datetime'), local_tz='Europe/Berlin')
        assert value == datetime.datetime(2026, 8, 5, 12, 0, tzinfo=datetime.timezone.utc)

    def test_timedelta_parsed(self):
        assert field_value(_widget('PT1H30M'), Field(widget_type='timedelta')) == datetime.timedelta(hours=1, minutes=30)

    def test_input_chips_splits_comma_separated_entries(self):
        value = field_value(_widget(['a', 'b, c']), Field(widget_type='ui.input_chips'))
        assert value == ['a', 'b', 'c']

    def test_slider_int_field_type(self):
        value = field_value(_widget(7.0), Field(widget_type='ui.slider', field_type=int))
        assert value == 7
        assert type(value) is int

    def test_multiselect_empty_stays_list_for_non_optional(self):
        fi = Field(widget_type='ui.select', multiple=True, options=['a'], field_type=list[str])
        assert field_value(_widget([]), fi) == []

    def test_multiselect_empty_becomes_none_for_optional(self):
        fi = Field(widget_type='ui.select', multiple=True, options=['a'], field_type=Optional[list[str]])
        assert field_value(_widget([]), fi) is None

    def test_checkbox_group_returns_list(self):
        fi = Field(widget_type='checkbox_group', options=['a', 'b'])
        assert field_value(_widget(['a']), fi) == ['a']

    def test_comma_separated_input_for_list_field_type(self):
        fi = Field(widget_type='ui.input', field_type=list[int], item_type=int)
        assert field_value(_widget('1, 2, 3'), fi) == [1, 2, 3]


# ---------------------------------------------------------------------------
# error handling (no NiceGUI context needed — these raise before rendering)
# ---------------------------------------------------------------------------

class TestErrors:
    def test_render_field_requires_field_info(self):
        with pytest.raises(TypeError):
            render_field('not a field info')  # type: ignore[arg-type]

    def test_render_field_requires_widget_type(self):
        with pytest.raises(ValueError, match='widget_type'):
            render_field(Field(label='Name'))

    @pytest.mark.parametrize('widget_type', ['editgrid', 'modelselect'])
    def test_render_field_rejects_model_only_widgets(self, widget_type):
        with pytest.raises(ValueError, match='ModelForm'):
            render_field(Field(widget_type=widget_type))  # type: ignore[typeddict-item]

    def test_field_value_requires_widget_type(self):
        with pytest.raises(ValueError, match='widget_type'):
            field_value(_widget('x'), Field(label='Name'))

    @pytest.mark.parametrize('widget_type', ['editgrid', 'modelselect'])
    def test_field_value_rejects_model_only_widgets(self, widget_type):
        with pytest.raises(ValueError, match='ModelForm'):
            field_value(_widget('x'), Field(widget_type=widget_type))  # type: ignore[typeddict-item]

    def test_list_input_without_item_type_raises(self):
        fi = Field(widget_type='ui.input', field_type=list[int])
        with pytest.raises(ValueError, match='item type'):
            field_value(_widget('1, 2'), fi)


class TestPublicApi:
    def test_exported_from_package(self):
        assert niceview.render_field is render_field
        assert niceview.field_value is field_value
        assert niceview.to_widget_value is to_widget_value


# ---------------------------------------------------------------------------
# validation layer 1: required and the widget-level validation callback
# ---------------------------------------------------------------------------

class TestRequired:
    @pytest.mark.parametrize('value', [None, '', [], {}])
    def test_empty_values(self, value):
        assert niceview.widgets.is_empty(value) is True

    @pytest.mark.parametrize('value', [False, 0, 0.0, 'x', ['a'], datetime.date(2026, 8, 5)])
    def test_non_empty_values(self, value):
        # A required switch may be False and a required number may be 0.
        assert niceview.widgets.is_empty(value) is False

    def test_required_field_rejects_empty(self):
        fi = Field(widget_type='ui.input', required=True)
        assert niceview.widgets.required_error(fi, '') == 'Required'
        assert niceview.widgets.required_error(fi, 'Alice') is None

    def test_custom_message(self):
        fi = Field(widget_type='ui.input', required=True)
        assert niceview.widgets.required_error(fi, '', 'Pflichtfeld') == 'Pflichtfeld'

    def test_optional_field_accepts_empty(self):
        assert niceview.widgets.required_error(Field(widget_type='ui.input'), '') is None

    def test_disabled_required_field_is_not_checked(self):
        # A disabled empty field must not be able to block a form forever.
        fi = Field(widget_type='ui.input', required=True, editable=False)
        assert niceview.widgets.required_error(fi, '') is None


class TestRunValidation:
    def test_callable_message(self):
        assert niceview.widgets.run_validation(lambda v: 'too short' if len(v) < 3 else None, 'ab') == 'too short'

    def test_callable_ok(self):
        assert niceview.widgets.run_validation(lambda v: None, 'abc') is None

    def test_dict_first_failing_message(self):
        rules = {'too short': lambda v: len(v) >= 3, 'no digits': lambda v: v.isalpha()}
        assert niceview.widgets.run_validation(rules, 'ab') == 'too short'
        assert niceview.widgets.run_validation(rules, 'a1') == 'too short'   # both fail, first wins
        assert niceview.widgets.run_validation(rules, 'abc1') == 'no digits'
        assert niceview.widgets.run_validation(rules, 'abcd') is None

    def test_none_validation(self):
        assert niceview.widgets.run_validation(None, 'anything') is None


class TestWithoutProp:
    """
    _without_prop() keeps a niceview layout directive from leaking into the widget as an HTML
    attribute — 'inline' selects row vs column for a checkbox_group and means nothing to Quasar.
    """

    def test_removes_the_token(self):
        fi = Field(widget_type='checkbox_group', props='inline dense')
        assert niceview.widgets._without_prop(fi, 'inline').props == 'dense'

    def test_leaves_the_original_untouched(self):
        fi = Field(widget_type='checkbox_group', props='inline dense')
        niceview.widgets._without_prop(fi, 'inline')
        assert fi.props == 'inline dense'

    def test_only_the_whole_token_matches(self):
        fi = Field(widget_type='checkbox_group', props='inline-block')
        assert niceview.widgets._without_prop(fi, 'inline').props == 'inline-block'

    def test_no_props_is_passed_through(self):
        fi = Field(widget_type='checkbox_group')
        assert niceview.widgets._without_prop(fi, 'inline').props is None


class TestResolveHelpTexts:
    """
    Where a field's `description` ends up. Explicit beats derived, and a description never
    fills the slot it was not assigned to.
    """
    resolve = staticmethod(niceview.widgets.resolve_help_texts)

    def test_description_becomes_the_tooltip_by_default(self):
        fi = Field(widget_type='ui.input', description='what it means')
        assert self.resolve(fi) == (None, 'what it means')

    def test_description_becomes_the_hint_when_asked(self):
        fi = Field(widget_type='ui.input', description='what it means')
        assert self.resolve(fi, 'hint') == ('what it means', None)

    def test_description_is_dropped_when_switched_off(self):
        fi = Field(widget_type='ui.input', description='what it means')
        assert self.resolve(fi, None) == (None, None)

    def test_explicit_tooltip_wins_over_the_description(self):
        fi = Field(widget_type='ui.input', description='derived', tooltip='mine')
        assert self.resolve(fi, 'tooltip') == (None, 'mine')

    def test_explicit_hint_wins_over_the_description(self):
        fi = Field(widget_type='ui.input', description='derived', hint='mine')
        assert self.resolve(fi, 'hint') == ('mine', None)

    def test_a_description_never_fills_the_other_slot(self):
        # hint is taken, but the description was assigned to the tooltip: it stays there
        fi = Field(widget_type='ui.input', description='derived', hint='mine')
        assert self.resolve(fi, 'tooltip') == ('mine', 'derived')

    def test_both_explicit_are_both_kept(self):
        fi = Field(widget_type='ui.input', description='derived', hint='h', tooltip='t')
        assert self.resolve(fi, 'tooltip') == ('h', 't')

    def test_empty_explicit_value_suppresses_the_description(self):
        # '' is assigned, so the slot counts as taken — an explicit way to say 'nothing here'
        fi = Field(widget_type='ui.input', description='derived', tooltip='')
        assert self.resolve(fi, 'tooltip') == (None, '')

    def test_no_description_leaves_both_alone(self):
        fi = Field(widget_type='ui.input', hint='h')
        assert self.resolve(fi, 'tooltip') == ('h', None)

    def test_explicitness_survives_a_field_info_merge(self):
        # a tooltip set in Meta.field_infos / ModelForm(field_infos=) must win just as one
        # set on the model field does
        base = Field(widget_type='ui.input', description='derived')
        merged = niceview.fieldinfo._merge_field_infos(base, Field(tooltip='from meta'))
        assert self.resolve(merged, 'tooltip') == (None, 'from meta')


class TestReservesBottomSpace:
    """
    Whether a field is taller than its box. Quasar keeps 20px free below a field that can show
    a message; a form action beside it has to know, or it sits half of that too low.
    """
    reserves = staticmethod(niceview.widgets.reserves_bottom_space)

    def test_a_validated_widget_reserves_it(self):
        # ModelForm wires a validation on every one of them, which is what makes NiceGUI
        # reserve the space (error=False) — no rule of the field's own is needed.
        assert self.reserves(Field(widget_type='ui.input')) is True
        assert self.reserves(Field(widget_type='ui.select')) is True

    def test_a_control_widget_does_not(self):
        assert self.reserves(Field(widget_type='ui.switch')) is False
        assert self.reserves(Field(widget_type='ui.slider')) is False
        assert self.reserves(Field(widget_type='checkbox_group')) is False

    def test_a_hint_reserves_it_on_a_widget_with_a_hint_slot(self):
        assert self.reserves(Field(widget_type='ui.color_input', hint='#rrggbb')) is True
        assert self.reserves(Field(widget_type='ui.color_input')) is False

    def test_a_hint_the_widget_cannot_show_reserves_nothing(self):
        assert self.reserves(Field(widget_type='ui.switch', hint='dropped')) is False

    def test_a_description_shown_as_a_hint_counts(self):
        fi = Field(widget_type='ui.color_input', description='what it means')
        assert self.reserves(fi, 'hint') is True
        assert self.reserves(fi, 'tooltip') is False

    def test_an_unknown_widget_type_reserves_nothing(self):
        assert self.reserves(Field()) is False
        assert self.reserves(Field(widget_type='editgrid')) is False


class TestParseTimedelta:
    """Tolerant timedelta input: ISO 8601 (case-insensitive, incl. P1Y/P1M/P1W) and human
    shorthand, always resolving to a timedelta the field then shows canonically."""

    def _canonical(self, td: datetime.timedelta) -> str:
        return to_widget_value(Field(widget_type='timedelta'), td)

    @pytest.mark.parametrize('text, expected', [
        ('P7D', datetime.timedelta(days=7)),
        ('p7d', datetime.timedelta(days=7)),                 # lower case
        ('pt1h30m', datetime.timedelta(hours=1, minutes=30)),
        ('P1Y', datetime.timedelta(days=365)),               # pydantic's fixed lengths
        ('P1M', datetime.timedelta(days=30)),                # month before the T
        ('P1W', datetime.timedelta(days=7)),
        ('7d', datetime.timedelta(days=7)),                  # shorthand
        ('2h30m', datetime.timedelta(hours=2, minutes=30)),
        ('1d2h', datetime.timedelta(days=1, hours=2)),
        ('90m', datetime.timedelta(minutes=90)),
        ('1w', datetime.timedelta(weeks=1)),
        ('1.5h', datetime.timedelta(hours=1, minutes=30)),   # decimals
        ('2h 30m', datetime.timedelta(hours=2, minutes=30)), # spaces
        ('1y', datetime.timedelta(days=365)),
        ('-2h', datetime.timedelta(hours=-2)),               # sign
    ])
    def test_accepts_tolerant_forms(self, text, expected):
        assert niceview.widgets.parse_timedelta(text) == expected

    def test_empty_is_none(self):
        assert niceview.widgets.parse_timedelta('') is None
        assert niceview.widgets.parse_timedelta('   ') is None

    @pytest.mark.parametrize('text', ['7', 'abc', '2x3d', 'PT7D', '5 apples'])
    def test_rejects_ambiguous_or_invalid(self, text):
        # A bare number is rejected on purpose: pydantic would read '7' as 7 seconds.
        with pytest.raises(Exception):
            niceview.widgets.parse_timedelta(text)

    def test_shorthand_and_iso_share_the_canonical_form(self):
        # '7d', 'p7d' and 'P1W' all mean 7 days and display the same afterwards.
        for text in ('7d', 'p7d', 'P1W', '1w'):
            assert self._canonical(niceview.widgets.parse_timedelta(text)) == 'P7D'

    def test_field_value_uses_the_tolerant_parser(self):
        assert field_value(_widget('2h30m'), Field(widget_type='timedelta')) == datetime.timedelta(hours=2, minutes=30)
