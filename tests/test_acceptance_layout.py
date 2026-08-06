"""
Acceptance tests for form layouts: rows, sections and the styling cascade.

The notation lives in Meta.profiles or in layout=; what is checked here is what it renders —
which container a widget ends up in, and which classes and props it carries.
"""
import pydantic
from nicegui import ui
from nicegui.testing import User
from typing import Annotated

import niceview
from niceview import ModelForm


class Address(pydantic.BaseModel):
    name: str = 'Alice'
    street: str = 'Main Street 1'
    zip_code: str = '12345'
    city: str = 'Berlin'
    notes: str = ''

    class Meta:
        profiles = {
            'detail': [
                'name',
                ['# Address', 'street', ['zip_code:sm:w-1/3', 'city']],
                'notes',
            ],
        }


def _form(build) -> list:
    captured: list = []

    @ui.page('/')
    def page():
        captured.append(build())

    return captured


def _parent(widget) -> ui.element:
    return widget.parent_slot.parent


class TestRows:
    async def test_fields_of_a_row_share_a_container(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(Address(), layout=['name', ['zip_code', 'city']]).render())
        await user.open('/')
        form = captured[0]

        row = _parent(form.w('zip_code'))
        assert isinstance(row, ui.row)
        assert _parent(form.w('city')) is row
        assert _parent(form.w('name')) is not row

    async def test_row_fields_share_the_width_evenly(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(Address(), layout=[['zip_code', 'city']]).render())
        await user.open('/')
        assert 'flex-1' in captured[0].w('zip_code')._classes

    async def test_a_field_hint_replaces_the_even_split(self, user: User) -> None:
        # 'flex-1' would set flex-basis to 0 and silently win over any width the layout asks for.
        captured = _form(lambda: ModelForm.from_item(Address(), layout=[['zip_code:sm:w-1/3', 'city']]).render())
        await user.open('/')
        widget = captured[0].w('zip_code')
        assert 'sm:w-1/3' in widget._classes
        assert 'flex-1' not in widget._classes
        assert 'min-w-0' in widget._classes

    async def test_row_classes_replace_the_defaults(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(Address(), layout=[[':gap-8 items-end', 'zip_code', 'city']]).render())
        await user.open('/')
        row = _parent(captured[0].w('zip_code'))
        assert 'gap-8' in row._classes and 'items-end' in row._classes
        assert 'gap-4' not in row._classes

    async def test_nesting_alternates(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(Address(), layout=[['name', ['street', 'city']]]).render())
        await user.open('/')
        form = captured[0]
        assert isinstance(_parent(form.w('name')), ui.row)
        assert isinstance(_parent(form.w('street')), ui.column)


class TestSections:
    async def test_titled_group_renders_a_card_with_its_title(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(Address(), profile='detail').render())
        await user.open('/')
        await user.should_see('Address')

        card = _parent(captured[0].w('street'))
        assert isinstance(card, ui.card)
        assert card._props.get('flat') and card._props.get('bordered')

    async def test_a_row_inside_a_section(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(Address(), profile='detail').render())
        await user.open('/')
        form = captured[0]

        row = _parent(form.w('zip_code'))
        assert isinstance(row, ui.row)
        assert isinstance(_parent(row), ui.card)

    async def test_fields_outside_the_section_stay_outside(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(Address(), profile='detail').render())
        await user.open('/')
        form = captured[0]
        assert not isinstance(_parent(form.w('name')), (ui.card, ui.row))


class TestStylingCascade:
    async def test_field_props_and_classes_reach_every_widget(self, user: User) -> None:
        class Mixed(pydantic.BaseModel):
            text: str = 'x'
            choice: Annotated[str, niceview.Field(widget_type='ui.select', options=['a', 'b'])] = 'a'
            tags: list[str] = pydantic.Field(default_factory=list)

        captured = _form(lambda: ModelForm.from_item(Mixed(), field_props='outlined dense',
                                                     field_classes='w-full').render())
        await user.open('/')
        form = captured[0]
        for name in ('text', 'choice', 'tags'):
            widget = form.w(name)
            assert widget._props.get('outlined') is True, name      # not just ui.input
            assert widget._props.get('dense') is True, name
            assert 'w-full' in widget._classes, name

    async def test_field_info_wins_over_the_form_default(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            a: Annotated[str, niceview.Field(props='filled')] = 'x'

        captured = _form(lambda: ModelForm.from_item(Item(), field_props='outlined').render())
        await user.open('/')
        widget = captured[0].w('a')
        # both are applied, the field's own props last
        assert widget._props.get('filled') is True and widget._props.get('outlined') is True

    async def test_cascade_order_form_then_field_then_layout(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            a: Annotated[str, niceview.Field(classes='text-right')] = 'x'

        captured = _form(lambda: ModelForm.from_item(Item(), field_classes='w-full',
                                                     layout=[['a:sm:w-1/2']]).render())
        await user.open('/')
        classes = captured[0].w('a')._classes
        assert classes.index('w-full') < classes.index('text-right') < classes.index('sm:w-1/2')

    async def test_render_field_honours_the_form_defaults(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            a: str = 'x'

        def build():
            form = ModelForm.from_item(Item(), field_props='outlined dense')
            form.render_field('a')
            return form

        captured = _form(build)
        await user.open('/')
        assert captured[0].w('a')._props.get('dense') is True


class TestCompatibility:
    async def test_without_a_layout_fields_are_direct_children(self, user: User) -> None:
        # The two-column ui.grid() wrapper in examples/02 relies on this: no layout means no
        # container of our own, so the fields flow into whatever the caller opened.
        def build():
            with ui.grid().classes('grid-cols-2') as grid:
                form = ModelForm.from_item(Address()).render()
            return form, grid

        captured = _form(build)
        await user.open('/')
        form, grid = captured[0]
        assert _parent(form.w('name')) is grid
        assert _parent(form.w('city')) is grid

    async def test_hidden_field_in_a_layout_is_skipped(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            a: str = 'x'
            secret: Annotated[str, niceview.Field(hidden=True)] = 'y'

        captured = _form(lambda: ModelForm.from_item(Item(), layout=[['a', 'secret']]).render())
        await user.open('/')
        form = captured[0]
        assert 'a' in form.widgets and 'secret' not in form.widgets

    async def test_validation_still_works_inside_a_layout(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            first: str = 'a'
            second: str = 'b'

            @pydantic.model_validator(mode='after')
            def different(self):
                if self.first == self.second:
                    raise ValueError('first and second must differ')
                return self

        captured = _form(lambda: ModelForm.from_item(Item(), layout=[['# Pair', 'first', 'second']]).render())
        await user.open('/')
        form = captured[0]

        user.find('First').clear().type('b').trigger('blur')
        await user.should_see('first and second must differ')
        assert form.item.first == 'a'
