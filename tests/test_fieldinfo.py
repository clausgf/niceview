import pytest
from niceview.fieldinfo import FieldInfo


class TestDefaults:
    def test_label_is_empty_string(self):
        assert FieldInfo().label == ''

    def test_editable_is_true(self):
        assert FieldInfo().editable is True

    def test_hidden_is_false(self):
        assert FieldInfo().hidden is False

    def test_required_is_false(self):
        assert FieldInfo().required is False

    def test_widget_type_is_none(self):
        assert FieldInfo().widget_type is None

    def test_min_max_are_none(self):
        fi = FieldInfo()
        assert fi.min is None
        assert fi.max is None

    def test_placeholder_is_none(self):
        assert FieldInfo().placeholder is None


class TestInit:
    def test_set_label(self):
        assert FieldInfo(label='My Label').label == 'My Label'

    def test_set_widget_type(self):
        assert FieldInfo(widget_type='ui.input').widget_type == 'ui.input'

    def test_set_min_max(self):
        fi = FieldInfo(min=1.0, max=99.0)
        assert fi.min == 1.0
        assert fi.max == 99.0

    def test_set_editable_false(self):
        assert FieldInfo(editable=False).editable is False

    def test_set_hidden(self):
        assert FieldInfo(hidden=True).hidden is True

    def test_none_value_does_not_override_default(self):
        # None is explicitly ignored in __init__
        fi = FieldInfo(label=None)
        assert fi.label == ''

    def test_invalid_kwarg_raises_value_error(self):
        with pytest.raises(ValueError, match='Invalid field name'):
            FieldInfo(not_a_real_field='value')

    def test_set_tooltip(self):
        assert FieldInfo(tooltip='Hint text').tooltip == 'Hint text'

    def test_set_classes(self):
        assert FieldInfo(classes='text-red-500').classes == 'text-red-500'

    def test_set_radio_options_list(self):
        fi = FieldInfo(radio_options=['a', 'b', 'c'])
        assert fi.radio_options == ['a', 'b', 'c']

    def test_set_radio_options_dict(self):
        fi = FieldInfo(radio_options={'a': 'Option A', 'b': 'Option B'})
        assert fi.radio_options == {'a': 'Option A', 'b': 'Option B'}

    def test_set_widget_type_radio(self):
        fi = FieldInfo(widget_type='ui.radio')
        assert fi.widget_type == 'ui.radio'


class TestRepr:
    def test_repr_is_non_empty(self):
        assert repr(FieldInfo())

    def test_repr_contains_label(self):
        assert 'MyLabel' in repr(FieldInfo(label='MyLabel'))

    def test_repr_contains_widget_type(self):
        assert 'ui.number' in repr(FieldInfo(widget_type='ui.number'))
