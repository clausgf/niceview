"""
Acceptance tests for the model-free renderer `niceview.render_field()`.

Scope: that a FieldInfo alone — no Pydantic model, no ModelForm — renders the same widget
with the same styling ModelForm would produce, and that the widget round-trips through
field_value(). Uses the NiceGUI User fixture (headless, no browser).
"""
import asyncio
import datetime

import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User
from typing import Annotated

import niceview
from niceview import CheckboxGroup, Field, ModelForm, field_value, render_field


def _page(build):
    """Register '/' with a page that runs build() and captures its return value."""
    captured: list = []

    @ui.page('/')
    def page():
        captured.append(build())

    return captured


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------

class TestRenderFieldWidgets:
    async def test_input_with_label_and_value(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Name', widget_type='ui.input'), 'Alice'))

        await user.open('/')
        await user.should_see('Name')
        assert isinstance(captured[0], ui.input)
        assert captured[0].value == 'Alice'

    async def test_number(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Age', widget_type='ui.number', min=0, max=120), 30))

        await user.open('/')
        await user.should_see(ui.number)
        assert captured[0].value == 30
        assert captured[0]._props['min'] == 0

    async def test_textarea(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Bio', widget_type='ui.textarea'), 'hello'))

        await user.open('/')
        assert isinstance(captured[0], ui.textarea)
        assert captured[0].value == 'hello'

    async def test_switch(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Active', widget_type='ui.switch'), True))

        await user.open('/')
        await user.should_see('Active')
        assert captured[0].value is True

    async def test_checkbox(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Agree', widget_type='ui.checkbox'), False))

        await user.open('/')
        await user.should_see('Agree')
        assert captured[0].value is False

    async def test_select_with_options(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Color', widget_type='ui.select', options=['red', 'green']), 'green'))

        await user.open('/')
        assert captured[0].options == ['red', 'green']
        assert captured[0].value == 'green'

    async def test_radio_with_options(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(widget_type='ui.radio', options=['red', 'green']), 'red'))

        await user.open('/')
        assert isinstance(captured[0], ui.radio)
        assert captured[0].options == ['red', 'green']
        assert captured[0].value == 'red'

    async def test_toggle_with_options(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(widget_type='ui.toggle', options=['on', 'off']), 'off'))

        await user.open('/')
        assert isinstance(captured[0], ui.toggle)
        assert captured[0].value == 'off'

    async def test_checkbox_group(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(widget_type='checkbox_group', options=['read', 'write']), ['write']))

        await user.open('/')
        await user.should_see('read')
        group = captured[0]
        assert isinstance(group, CheckboxGroup)
        assert group.value == ['write']

    async def test_input_chips(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Tags', widget_type='ui.input_chips'), ['a', 'b']))

        await user.open('/')
        assert captured[0].value == ['a', 'b']

    async def test_color_input(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Color', widget_type='ui.color_input'), '#ff0000'))

        await user.open('/')
        assert isinstance(captured[0], ui.color_input)
        assert captured[0].value == '#ff0000'

    async def test_date(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Start', widget_type='date'), datetime.date(2026, 8, 5)))

        await user.open('/')
        assert captured[0].value == '2026-08-05'
        assert captured[0]._props['type'] == 'date'

    async def test_time(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='At', widget_type='time'), datetime.time(14, 30)))

        await user.open('/')
        assert captured[0].value == '14:30:00'
        assert captured[0]._props['type'] == 'time'

    async def test_datetime(self, user: User) -> None:
        value = datetime.datetime(2026, 8, 5, 12, 0, tzinfo=datetime.timezone.utc)
        captured = _page(lambda: render_field(Field(label='When', widget_type='datetime'), value, local_tz='Europe/Berlin'))

        await user.open('/')
        assert captured[0].value == '2026-08-05T14:00:00'
        assert captured[0]._props['type'] == 'datetime-local'

    async def test_timedelta(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Every', widget_type='timedelta'), datetime.timedelta(minutes=90)))

        await user.open('/')
        assert captured[0].value == 'PT1H30M'

    async def test_slider(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Level', widget_type='ui.slider', min=0, max=10), 7))

        await user.open('/')
        await user.should_see('Level')
        assert isinstance(captured[0], ui.slider)
        assert captured[0].value == 7

    async def test_rating(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Stars', widget_type='ui.rating', max=10), 3))

        await user.open('/')
        assert isinstance(captured[0], ui.rating)
        assert captured[0].value == 3
        assert captured[0]._props['max'] == 10

    async def test_string_value_for_date_passes_through(self, user: User) -> None:
        # JSON-sourced values are strings already; no pre-conversion required.
        captured = _page(lambda: render_field(Field(label='Start', widget_type='date'), '2026-08-05'))

        await user.open('/')
        assert captured[0].value == '2026-08-05'

    async def test_unknown_widget_type_raises(self, user: User) -> None:
        fi = Field(label='X')
        fi.widget_type = 'ui.nonexistent'  # type: ignore[assignment]

        @ui.page('/')
        def page():
            with pytest.raises(ValueError, match='Invalid widget class'):
                render_field(fi)

        await user.open('/')


# ---------------------------------------------------------------------------
# field_info attributes
# ---------------------------------------------------------------------------

class TestFieldInfoApplied:
    async def test_props_classes_style_applied(self, user: User) -> None:
        fi = Field(label='Name', widget_type='ui.input', props='outlined dense', classes='w-full', style='color: red')
        captured = _page(lambda: render_field(fi))

        await user.open('/')
        widget = captured[0]
        assert widget._props.get('outlined') is True
        assert widget._props.get('dense') is True
        assert 'w-full' in widget._classes
        assert 'color: red' in ';'.join(f'{k}: {v}' for k, v in widget._style.items())

    async def test_placeholder_applied(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Name', widget_type='ui.input', placeholder='e.g. Alice')))

        await user.open('/')
        assert captured[0]._props['placeholder'] == 'e.g. Alice'

    async def test_not_editable_disables_widget(self, user: User) -> None:
        captured = _page(lambda: render_field(Field(label='Name', widget_type='ui.input', editable=False), 'x'))

        await user.open('/')
        assert captured[0].enabled is False

    async def test_not_editable_disables_checkbox_group(self, user: User) -> None:
        fi = Field(widget_type='checkbox_group', options=['read', 'write'], editable=False)
        captured = _page(lambda: render_field(fi, ['read']))

        await user.open('/')
        assert all(not cb.enabled for cb in captured[0].checkboxes.values())

    async def test_validation_from_field_info_applied(self, user: User) -> None:
        fi = Field(label='Name', widget_type='ui.input',
                   validation=lambda v: 'too short' if len(v or '') < 3 else None)
        captured = _page(lambda: render_field(fi, 'ab'))

        await user.open('/')
        widget = captured[0]
        assert widget.validate() is False
        assert widget.error == 'too short'

    async def test_async_options_arrive_late(self, user: User) -> None:
        async def load_options() -> list[str]:
            await asyncio.sleep(0.01)
            return ['red', 'green']

        fi = Field(label='Color', widget_type='ui.select', options=load_options)
        captured = _page(lambda: render_field(fi, 'green'))

        await user.open('/')
        assert captured[0].options == []
        await asyncio.sleep(0.05)
        assert captured[0].options == ['red', 'green']
        assert captured[0].value == 'green'  # the initial value survives the option swap


# ---------------------------------------------------------------------------
# round trip and equivalence with ModelForm
# ---------------------------------------------------------------------------

class TestRoundTrip:
    async def test_value_read_back_after_edit(self, user: User) -> None:
        fi = Field(label='Age', widget_type='ui.number', field_type=int)
        captured = _page(lambda: render_field(fi, 30))

        await user.open('/')
        user.find(ui.number).type('9')  # appends to '30'
        assert field_value(captured[0], fi) == 309

    async def test_form_of_several_fields_collected(self, user: User) -> None:
        fields = {
            'name': Field(label='Name', widget_type='ui.input'),
            'age': Field(label='Age', widget_type='ui.number', field_type=int),
            'active': Field(label='Active', widget_type='ui.switch'),
            'start': Field(label='Start', widget_type='date'),
            'color': Field(label='Color', widget_type='ui.select', options=['red', 'green']),
            'tags': Field(label='Tags', widget_type='ui.input_chips'),
        }
        values = {'name': 'Alice', 'age': 30, 'active': True, 'start': datetime.date(2026, 8, 5),
                  'color': 'green', 'tags': ['a']}

        def build():
            with ui.column().classes('w-full'):
                return {key: render_field(fi, values[key]) for key, fi in fields.items()}

        captured = _page(build)

        await user.open('/')
        widgets = captured[0]
        assert {key: field_value(w, fields[key]) for key, w in widgets.items()} == values

    async def test_widget_matches_modelform(self, user: User) -> None:
        """The same FieldInfo must produce the same widget in both paths."""
        class Item(pydantic.BaseModel):
            name: Annotated[str, niceview.Field(label='Name', props='outlined dense', classes='w-full')] = 'Alice'

        captured: list = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item()).render()
            standalone = render_field(
                Field(label='Name', widget_type='ui.input', props='outlined dense', classes='w-full'),
                'Alice',
            )
            captured.append((form.w('name'), standalone))

        await user.open('/')
        from_form, standalone = captured[0]
        # 'for' is the element id; 'error'/'error-message' come from ModelForm's validation
        # wiring, which is exactly the part render_field() leaves to the caller.
        ignored = {'for', 'error', 'error-message'}

        def styling(widget):
            return {k: v for k, v in widget._props.items() if k not in ignored}

        assert type(from_form) is type(standalone)
        assert styling(from_form) == styling(standalone)
        assert from_form._classes == standalone._classes
        assert from_form.value == standalone.value
