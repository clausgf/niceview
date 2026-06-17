"""
Spike: NiceGUI User fixture smoke tests.

Goal: verify that the User fixture works with our render patterns before
committing to a full acceptance test suite.
"""
import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User

from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGrid, ModelGridInlineEdit
from niceview.modeledit import EditGridWrapper


class Person(pydantic.BaseModel):
    name: str = pydantic.Field(default='', max_length=20, title='Name')
    age: int = pydantic.Field(default=0, ge=0, le=120, title='Age')


# ---------------------------------------------------------------------------
# ModelForm: render + label visibility
# ---------------------------------------------------------------------------

async def test_form_renders_field_labels(user: User) -> None:
    @ui.page('/')
    def page():
        ModelForm.from_item(Person(name='Alice', age=30)).render()

    await user.open('/')
    await user.should_see('Name')
    await user.should_see('Age')


async def test_form_typing_updates_model(user: User) -> None:
    person = Person(name='Alice', age=30)

    @ui.page('/')
    def page():
        ModelForm.from_item(person).render()

    await user.open('/')
    user.find('Name').clear().type('Bob')
    user.find('Name').trigger('blur')
    assert person.name == 'Bob'


async def test_form_invalid_input_keeps_model_unchanged(user: User) -> None:
    person = Person(name='Alice', age=30)

    @ui.page('/')
    def page():
        ModelForm.from_item(person).render()

    await user.open('/')
    # name longer than max_length=20 is invalid; model must not be updated
    user.find('Name').clear().type('A' * 25)
    user.find('Name').trigger('blur')
    assert person.name == 'Alice'


# ---------------------------------------------------------------------------
# ModelGrid: render — AgGrid rows are JavaScript-rendered, not in DOM.
# Only the widget element and column headers are verifiable via User fixture.
# ---------------------------------------------------------------------------

async def test_grid_renders_aggrid_element(user: User) -> None:
    items = [Person(name='Alice', age=30), Person(name='Bob', age=25)]

    @ui.page('/')
    def page():
        ModelGrid.from_list(Person, items).render()

    await user.open('/')
    await user.should_see(ui.aggrid)


# ---------------------------------------------------------------------------
# EditGridWrapper: render + button visibility
# ---------------------------------------------------------------------------

async def test_editgridwrapper_renders_buttons(user: User) -> None:
    items: list[Person] = []

    @ui.page('/')
    def page():
        EditGridWrapper(ModelGrid.from_list(Person, items), title='People').render()

    await user.open('/')
    await user.should_see('People')
    await user.should_see(ui.button, content='add')
