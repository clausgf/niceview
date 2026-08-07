"""
Acceptance tests for the layered validation model and the commit policy.

Layers, in order: `required` and `field_info.validation` (both work without a model), then the
value conversion, then — ModelForm only — the Pydantic model. The item is written only when it
validates as a whole, in place, so NiceGUI bindings survive.
"""
import asyncio
import datetime

import pydantic
from nicegui import ui
from nicegui.testing import User
from typing import Annotated

import niceview
from niceview import Field, ModelForm, field_value, render_field


def _form(build) -> list:
    captured: list = []

    @ui.page('/')
    def page():
        captured.append(build())

    return captured


def _tooltips_of(widget) -> list[str]:
    """
    The texts of the tooltips attached to a widget. NiceGUI's Element.tooltip() does not nest
    the tooltip inside the element — it creates it in the current slot and links it back with a
    'target' prop — so widget.descendants() would never find it.
    """
    target = f'#{widget.html_id}'
    return [e.text for e in widget.client.elements.values()
            if isinstance(e, ui.tooltip) and e.props.get('target') == target]


# ---------------------------------------------------------------------------
# layer order
# ---------------------------------------------------------------------------

class TestLayerOrder:
    async def test_required_before_own_validation_before_model(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: Annotated[str, pydantic.Field(max_length=3),
                            niceview.Field(validation=lambda v: 'no digits' if any(c.isdigit() for c in v) else None)]

        captured = _form(lambda: ModelForm.from_item(Item(name='ab')).render())
        await user.open('/')
        form = captured[0]

        user.find('Name').clear().trigger('blur')                  # empty -> layer 1a
        await user.should_see('Required')

        user.find('Name').type('a1').trigger('blur')               # own rule -> layer 1b
        await user.should_see('no digits')

        user.find('Name').clear().type('abcd').trigger('blur')     # model constraint -> layer 3
        await user.should_see('at most 3 characters')

        user.find('Name').clear().type('abc').trigger('blur')
        assert form.validation_errors == {}
        assert form.item.name == 'abc'

    async def test_widget_validation_also_blocks_the_commit(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: Annotated[str, niceview.Field(validation=lambda v: 'nope' if v == 'bad' else None)] = 'ok'

        captured = _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        form = captured[0]

        user.find('Name').clear().type('bad').trigger('blur')
        assert form.validation_errors == {'name': 'nope'}
        assert form.w('name').value == 'bad'   # the widget keeps what was typed
        assert form.item.name == 'ok'          # but it is not committed
        assert form.draft.name != 'bad'        # and a rejected value never reaches the draft

    async def test_dict_validation_supported(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: Annotated[str, niceview.Field(validation={'too short': lambda v: len(v or '') >= 3})] = 'abc'

        _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        user.find('Name').clear().type('ab').trigger('blur')
        await user.should_see('too short')

    async def test_async_validation_is_displayed(self, user: User) -> None:
        async def check(value: str) -> str | None:
            await asyncio.sleep(0.01)
            return 'taken' if value == 'alice' else None

        class Item(pydantic.BaseModel):
            name: Annotated[str, niceview.Field(validation=check)] = 'bob'

        _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')                  # must not raise NotImplementedError
        user.find('Name').clear().type('alice').trigger('blur')
        await asyncio.sleep(0.05)
        await user.should_see('taken')

    async def test_conversion_error_does_not_reach_the_model(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            when: datetime.date = datetime.date(2026, 8, 5)

        captured = _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        form = captured[0]

        form.w('when').value = 'not-a-date'
        form.w('when').run_method('blur')
        await user.should_see('Error interpreting widget value')
        assert form.item.when == datetime.date(2026, 8, 5)
        assert form.draft.when == datetime.date(2026, 8, 5)   # working copy untouched


# ---------------------------------------------------------------------------
# required
# ---------------------------------------------------------------------------

class TestRequired:
    async def test_marker_in_label(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str                       # no default -> required
            nick: str = ''                  # default -> optional

        captured = _form(lambda: ModelForm.from_item(Item(name='Alice')).render())
        await user.open('/')
        form = captured[0]
        assert form.w('name')._props['label'] == 'Name *'
        assert form.w('nick')._props['label'] == 'Nick'

    async def test_marker_can_be_switched_off(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str

        captured = _form(lambda: ModelForm.from_item(Item(name='Alice'), required_marker=None).render())
        await user.open('/')
        assert captured[0].w('name')._props['label'] == 'Name'

    async def test_empty_required_field_blocks_the_commit(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str

        captured = _form(lambda: ModelForm.from_item(Item(name='Alice')).render())
        await user.open('/')
        form = captured[0]

        user.find('Name').clear().trigger('blur')
        await user.should_see('Required')
        assert form.has_validation_errors
        assert form.item.name == 'Alice'

    async def test_false_and_zero_are_not_empty(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            flag: bool
            count: int

        captured = _form(lambda: ModelForm.from_item(Item(flag=True, count=5)).render())
        await user.open('/')
        form = captured[0]

        form.w('flag').value = False
        user.find(ui.number).clear().type('0').trigger('blur')
        assert form.validation_errors == {}
        assert form.item.flag is False
        assert form.item.count == 0

    async def test_custom_message(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str

        _form(lambda: ModelForm.from_item(Item(name='Alice'), required_message='Pflichtfeld').render())
        await user.open('/')
        user.find('Name').clear().trigger('blur')
        await user.should_see('Pflichtfeld')

    async def test_required_without_a_model(self, user: User) -> None:
        fi = Field(label='Name', widget_type='ui.input', required=True)
        captured = _form(lambda: render_field(fi, 'Alice'))

        await user.open('/')
        widget = captured[0]
        assert widget._props['label'] == 'Name *'
        widget.value = ''
        assert widget.validate() is False
        assert widget.error == 'Required'


# ---------------------------------------------------------------------------
# cross-field errors and the commit sweep
# ---------------------------------------------------------------------------

class Pair(pydantic.BaseModel):
    first: str = 'a'
    second: str = 'b'

    @pydantic.model_validator(mode='after')
    def different(self):
        if self.first == self.second:
            raise ValueError('first and second must differ')
        return self


class TestCrossFieldCommit:
    async def test_cross_field_error_blocks_the_write_back(self, user: User) -> None:
        events: list = []
        pair = Pair()
        captured = _form(lambda: ModelForm.from_item(pair, on_change=events.append).render())
        await user.open('/')
        form = captured[0]

        user.find('First').clear().type('b').trigger('blur')
        await user.should_see('first and second must differ')
        assert pair.first == 'a'          # not written
        assert form.draft.first == 'b'    # but held in the draft
        assert events == []

    async def test_pending_edits_commit_together_when_the_error_clears(self, user: User) -> None:
        events: list = []
        pair = Pair()
        captured = _form(lambda: ModelForm.from_item(pair, on_change=events.append).render())
        await user.open('/')
        form = captured[0]

        user.find('First').clear().type('b').trigger('blur')      # blocked: first == second
        user.find('Second').clear().type('c').trigger('blur')     # resolves it
        assert not form.has_validation_errors
        assert (pair.first, pair.second) == ('b', 'c')

        # one event per actually changed field, with the value each had at commit time
        assert {(e.field_name, e.previous_value, e.value) for e in events} == \
               {('first', 'a', 'b'), ('second', 'b', 'c')}

    async def test_save_refuses_while_a_cross_field_error_stands(self, user: User, tmp_path) -> None:
        path = tmp_path / 'pair.json'
        captured = _form(lambda: ModelForm.from_json(Pair, path).render())
        await user.open('/')
        form = captured[0]

        user.find('First').clear().type('b').trigger('blur')
        form.save(notify=False)
        assert 'first and second must differ' in ' '.join(form.nonfield_validation_errors)
        assert Pair.model_validate_json(path.read_text()).first == 'a'

    async def test_unchanged_fields_emit_no_event(self, user: User) -> None:
        events: list = []
        _form(lambda: ModelForm.from_item(Pair(), on_change=events.append).render())
        await user.open('/')

        user.find('First').clear().type('z').trigger('blur')
        assert [e.field_name for e in events] == ['first']


# ---------------------------------------------------------------------------
# in-place mutation (NiceGUI bindings)
# ---------------------------------------------------------------------------

class TestInPlace:
    async def test_item_identity_is_stable(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str = 'Alice'

        item = Item()
        captured = _form(lambda: ModelForm.from_item(item).render())
        await user.open('/')
        form = captured[0]

        user.find('Name').clear().type('Bob').trigger('blur')
        assert form.item is item
        assert item.name == 'Bob'

    async def test_binding_follows_a_committed_edit(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str = 'Alice'

        def build():
            form = ModelForm.from_item(Item()).render()
            ui.label().bind_text_from(form.item, 'name')
            return form

        _form(build)
        await user.open('/')
        user.find('Name').clear().type('Bob').trigger('blur')
        await user.should_see('Bob')

    async def test_identity_survives_save_and_refresh(self, user: User, tmp_path) -> None:
        class Item(pydantic.BaseModel):
            name: str = 'Alice'

        captured = _form(lambda: ModelForm.from_json(Item, tmp_path / 'item.json').render())
        await user.open('/')
        form = captured[0]
        item = form.item

        user.find('Name').clear().type('Bob').trigger('blur')
        form.save(notify=False)
        assert form.item is item
        form.refresh(notify=False)
        assert form.item is item
        assert item.name == 'Bob'


# ---------------------------------------------------------------------------
# frozen, hint, SecretStr
# ---------------------------------------------------------------------------

class TestModelMetadata:
    async def test_frozen_field_is_disabled(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str = 'Alice'
            created: str = pydantic.Field(default='2026-08-05', frozen=True)

        captured = _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        form = captured[0]
        assert form.w('created').enabled is False
        assert form.w('name').enabled is True

    async def test_frozen_model_disables_every_field(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            model_config = pydantic.ConfigDict(frozen=True)
            name: str = 'Alice'

        captured = _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        assert captured[0].w('name').enabled is False

    async def test_explicit_editable_overrides_frozen_with_a_warning(self, user: User, caplog) -> None:
        class Item(pydantic.BaseModel):
            created: Annotated[str, niceview.Field(editable=True)] = pydantic.Field(default='x', frozen=True)

        captured = _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        assert captured[0].w('created').enabled is True
        assert 'frozen' in caplog.text

    async def test_description_renders_as_tooltip(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str = pydantic.Field(default='Alice', description='Full legal name')

        captured = _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        widget = captured[0].w('name')
        assert 'hint' not in widget._props
        assert 'placeholder' not in widget._props
        assert _tooltips_of(widget) == ['Full legal name']

    async def test_description_as_hint_restores_the_old_placement(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str = pydantic.Field(default='Alice', description='Full legal name')

        captured = _form(lambda: ModelForm.from_item(Item(), description_as='hint').render())
        await user.open('/')
        assert captured[0].w('name')._props['hint'] == 'Full legal name'

    async def test_description_as_none_shows_it_nowhere(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: str = pydantic.Field(default='Alice', description='Full legal name')

        captured = _form(lambda: ModelForm.from_item(Item(), description_as=None).render())
        await user.open('/')
        widget = captured[0].w('name')
        assert 'hint' not in widget._props
        assert _tooltips_of(widget) == []

    async def test_explicit_hint_wins_over_the_description(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            name: Annotated[str, niceview.Field(hint='Mine')] = pydantic.Field(
                default='Alice', description='Full legal name')

        captured = _form(lambda: ModelForm.from_item(Item(), description_as='hint').render())
        await user.open('/')
        assert captured[0].w('name')._props['hint'] == 'Mine'

    async def test_secret_str_renders_as_password(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            token: pydantic.SecretStr = pydantic.SecretStr('s3cret')

        captured = _form(lambda: ModelForm.from_item(Item()).render())
        await user.open('/')
        form = captured[0]
        widget = form.w('token')
        assert widget._props['type'] == 'password'
        assert widget.value == 's3cret'          # the widget edits the plain text

        user.find('Token').clear().type('new-one').trigger('blur')
        assert isinstance(form.item.token, pydantic.SecretStr)
        assert form.item.token.get_secret_value() == 'new-one'


# ---------------------------------------------------------------------------
# render_field parity: layer 1 works the same without a form
# ---------------------------------------------------------------------------

class TestModelFreeParity:
    async def test_validation_and_required_without_a_model(self, user: User) -> None:
        fi = Field(label='Name', widget_type='ui.input', required=True,
                   validation=lambda v: 'no digits' if any(c.isdigit() for c in v) else None)
        captured = _form(lambda: render_field(fi, 'abc'))

        await user.open('/')
        widget = captured[0]

        widget.value = ''
        assert widget.validate(return_result=True) is False
        assert widget.error == 'Required'

        widget.value = 'a1'
        widget.validate(return_result=True)
        assert widget.error == 'no digits'

        widget.value = 'abc'
        assert widget.validate(return_result=True) is True
        assert field_value(widget, fi) == 'abc'


# ---------------------------------------------------------------------------
# editable reaches the grid too
# ---------------------------------------------------------------------------

class TestGridEditable:
    def test_non_editable_column_is_not_inline_editable(self) -> None:
        from niceview.fields import Fields
        from niceview.modelgrid import _collect_aggrid_cols

        class Item(pydantic.BaseModel):
            name: str = 'Alice'
            created: str = pydantic.Field(default='2026-08-05', frozen=True)
            locked: Annotated[str, niceview.Field(editable=False)] = 'x'

        cols = {c['field']: c for c in _collect_aggrid_cols(Fields(Item))}
        assert cols['created']['editable'] is False     # frozen in the model
        assert cols['locked']['editable'] is False      # declared non-editable
        assert 'editable' not in cols['name']           # left to the grid's defaultColDef
