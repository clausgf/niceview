"""
Acceptance tests using the NiceGUI User fixture (headless, no browser).

Scope: render paths and widget↔model interaction that cannot be covered by
pure unit tests. Each test defines its own @ui.page so tests are isolated.

Known limitations of the User fixture:
- AgGrid cell content is JS-rendered and not in the DOM → row data is not
  verifiable via should_see(); only the aggrid element type is detectable.
- ui.number with max= clamps input to the allowed range instead of
  discarding it; out-of-range numeric input becomes a valid clamped value.
"""
import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User
from typing import Annotated, Literal

import niceview
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit
from niceview.modeledit import EditGridWrapper


class Person(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=20, title='Name')
    age: int = pydantic.Field(default=0, ge=0, le=120, title='Age')
    active: bool = pydantic.Field(default=True, title='Active')


# ---------------------------------------------------------------------------
# ModelForm — render
# ---------------------------------------------------------------------------

class TestModelFormRender:
    async def test_field_labels_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(Person()).render()

        await user.open('/')
        await user.should_see('Name')
        await user.should_see('Age')
        await user.should_see('Active')

    async def test_title_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(Person(), title='Edit Person').render()

        await user.open('/')
        await user.should_see('Edit Person')

    async def test_input_widgets_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(Person()).render()

        await user.open('/')
        await user.should_see(ui.input)
        await user.should_see(ui.number)
        await user.should_see(ui.switch)


# ---------------------------------------------------------------------------
# ModelForm — widget → model interaction
# ---------------------------------------------------------------------------

class TestModelFormInteraction:
    async def test_typing_updates_string_field(self, user: User) -> None:
        person = Person(name='Alice', age=30)

        @ui.page('/')
        def page():
            ModelForm.from_item(person).render()

        await user.open('/')
        user.find('Name').clear().type('Bob')
        user.find('Name').trigger('blur')
        assert person.name == 'Bob'

    async def test_typing_updates_number_field(self, user: User) -> None:
        person = Person(name='Alice', age=30)

        @ui.page('/')
        def page():
            ModelForm.from_item(person).render()

        await user.open('/')
        user.find('Age').clear().type('42')
        user.find('Age').trigger('blur')
        assert person.age == 42

    async def test_invalid_string_too_long_keeps_model(self, user: User) -> None:
        person = Person(name='Alice', age=30)

        @ui.page('/')
        def page():
            ModelForm.from_item(person).render()

        await user.open('/')
        user.find('Name').clear().type('A' * 25)  # exceeds max_length=20
        user.find('Name').trigger('blur')
        assert person.name == 'Alice'

    async def test_on_change_callback_called(self, user: User) -> None:
        person = Person(name='Alice', age=30)
        called_with = {}

        def on_change(e):
            called_with['field'] = e.field_name
            called_with['new'] = e.value

        @ui.page('/')
        def page():
            ModelForm.from_item(person, on_change=on_change).render()

        await user.open('/')
        user.find('Name').clear().type('Bob')
        user.find('Name').trigger('blur')
        assert called_with.get('field') == 'name'
        assert called_with.get('new') == 'Bob'

    async def test_autosave_updates_model_without_save_button(self, user: User) -> None:
        person = Person(name='Alice', age=30)

        @ui.page('/')
        def page():
            ModelForm.from_item(person, autosave=True).render()

        await user.open('/')
        user.find('Name').clear().type('Carol')
        user.find('Name').trigger('blur')
        assert person.name == 'Carol'

    async def test_exclude_hides_field(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(Person(), exclude=['active']).render()

        await user.open('/')
        await user.should_see('Name')
        await user.should_not_see(ui.switch)


# ---------------------------------------------------------------------------
# ModelForm — ui.radio widget
# ---------------------------------------------------------------------------

class Choice(pydantic.BaseModel):
    # Literal auto-infers select_options; widget_type override picks them up as radio options
    color: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.radio')] = 'green'


class TestModelFormRadioWidget:
    async def test_radio_widget_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(Choice()).render()

        await user.open('/')
        await user.should_see(ui.radio)

    async def test_radio_initial_value_in_model(self, user: User) -> None:
        item = Choice(color='red')

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        await user.should_see(ui.radio)
        # model value unchanged after render
        assert item.color == 'red'

    async def test_radio_change_updates_model(self, user: User) -> None:
        item = Choice(color='green')

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        user.find('red').click()
        assert item.color == 'red'


# ---------------------------------------------------------------------------
# ModelGrid — render
# ---------------------------------------------------------------------------

class TestModelGridRender:
    async def test_aggrid_element_present(self, user: User) -> None:
        items = [Person(name='Alice', age=30), Person(name='Bob', age=25)]

        @ui.page('/')
        def page():
            ModelGrid.from_list(Person, items).render()

        await user.open('/')
        await user.should_see(ui.aggrid)

    async def test_empty_list_renders_grid(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelGrid.from_list(Person, []).render()

        await user.open('/')
        await user.should_see(ui.aggrid)

    async def test_inline_edit_renders_grid(self, user: User) -> None:
        items = [Person(name='Alice', age=30)]

        @ui.page('/')
        def page():
            ModelGridInlineEdit.from_list(Person, items).render()

        await user.open('/')
        await user.should_see(ui.aggrid)


# ---------------------------------------------------------------------------
# EditGridWrapper — render
# ---------------------------------------------------------------------------

class TestEditGridWrapperRender:
    async def test_title_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper(ModelGrid.from_list(Person, []), title='People').render()

        await user.open('/')
        await user.should_see('People')

    async def test_add_button_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper(ModelGrid.from_list(Person, [])).render()

        await user.open('/')
        await user.should_see(ui.button, content='add')

    async def test_delete_button_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper(ModelGrid.from_list(Person, [])).render()

        await user.open('/')
        await user.should_see(ui.button, content='delete')

    async def test_grid_element_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper(ModelGrid.from_list(Person, [])).render()

        await user.open('/')
        await user.should_see(ui.aggrid)
