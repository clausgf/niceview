"""
The FieldInfo <-> NiceGUI option contract.

niceview.Field() is meant to be NiceGUI's widget vocabulary plus a named set of extensions, not
a subset that drifts as NiceGUI evolves. This test holds that line: every constructor argument
of every supported element must be declared in WIDGET_OPTIONS as carried by a FieldInfo
attribute, owned by niceview, or deliberately left to props=. A NiceGUI upgrade that adds an
argument fails here instead of being silently ignored.
"""
import inspect

import pytest
from nicegui import ui

from niceview.fieldinfo import _FieldInfoInputs
from niceview.widgets import WIDGET_OPTIONS

# FieldInfo attribute -> NiceGUI keyword, where the two names deliberately differ.
RENAMED = {
    'text': 'label',              # ui.checkbox / ui.switch label
    'format': 'number_format',    # JSON Schema's `format` means widget_type, so ours is renamed
    'preview': 'color_preview',
}

WIDGET_ELEMENTS = {name: getattr(ui, name.removeprefix('ui.')) for name in WIDGET_OPTIONS}


def _parameters(element: type) -> set[str]:
    return {p for p in inspect.signature(element.__init__).parameters if p not in ('self', 'args', 'kwargs')}


@pytest.mark.parametrize('widget_type', sorted(WIDGET_OPTIONS))
def test_every_constructor_argument_is_declared(widget_type: str) -> None:
    buckets = WIDGET_OPTIONS[widget_type]
    declared = buckets['field_info'] | buckets['owned'] | buckets['via_props']
    actual = _parameters(WIDGET_ELEMENTS[widget_type])

    undeclared = actual - declared
    assert not undeclared, (
        f"{widget_type} accepts {sorted(undeclared)}, which WIDGET_OPTIONS does not mention. "
        f"Add it to 'field_info' (with a FieldInfo attribute), to 'owned', or to 'via_props'."
    )
    stale = declared - actual
    assert not stale, f"WIDGET_OPTIONS declares {sorted(stale)} for {widget_type}, which it does not accept"


@pytest.mark.parametrize('widget_type', sorted(WIDGET_OPTIONS))
def test_field_info_bucket_has_a_field_info_attribute(widget_type: str) -> None:
    attributes = set(_FieldInfoInputs.__annotations__)
    for option in WIDGET_OPTIONS[widget_type]['field_info']:
        name = RENAMED.get(option, option)
        assert name in attributes, (
            f"{widget_type}'s '{option}' is declared as carried by a FieldInfo attribute, "
            f"but '{name}' is not one. Add it, rename it in RENAMED, or move it to 'via_props'."
        )


def test_buckets_are_disjoint() -> None:
    for widget_type, buckets in WIDGET_OPTIONS.items():
        fi, owned, props = buckets['field_info'], buckets['owned'], buckets['via_props']
        assert not (fi & owned) and not (fi & props) and not (owned & props), \
            f"{widget_type}: an option is declared in more than one bucket"
