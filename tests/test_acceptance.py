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
import enum
import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User
from typing import Annotated, Literal

import niceview
from niceview.form import ModelForm
from niceview.grid import ModelGrid, ModelGridInlineEdit
from niceview.wrapper import EditFormWrapper, EditGridWrapper


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
            EditFormWrapper.from_item(Person(), title='Edit Person')

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
# ModelForm — slider widget
# ---------------------------------------------------------------------------

class SliderItem(pydantic.BaseModel):
    volume: Annotated[int, pydantic.Field(default=50, ge=0, le=100, title='Volume'), niceview.Field(widget_type='slider')]
    priority: Annotated[int, pydantic.Field(default=3, ge=1, le=5, title='Priority'), niceview.Field(widget_type='rating')]


class TestModelFormSliderWidget:
    async def test_slider_widget_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(SliderItem()).render()

        await user.open('/')
        await user.should_see(ui.slider)

    async def test_slider_label_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(SliderItem()).render()

        await user.open('/')
        await user.should_see('Volume')

    async def test_slider_initial_value_in_model(self, user: User) -> None:
        item = SliderItem(volume=75)

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        assert item.volume == 75

    async def test_slider_change_updates_model(self, user: User) -> None:
        item = SliderItem(volume=50)

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        slider = user.find(ui.slider).elements.pop()
        slider.value = 80
        slider.update()
        assert item.volume == 80


# ---------------------------------------------------------------------------
# ModelForm — rating widget
# ---------------------------------------------------------------------------

class TestModelFormRatingWidget:
    async def test_rating_widget_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(SliderItem()).render()

        await user.open('/')
        await user.should_see(ui.rating)

    async def test_rating_label_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(SliderItem()).render()

        await user.open('/')
        await user.should_see('Priority')

    async def test_rating_initial_value_in_model(self, user: User) -> None:
        item = SliderItem(priority=4)

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        assert item.priority == 4

    async def test_rating_change_updates_model(self, user: User) -> None:
        item = SliderItem(priority=3)

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        rating = user.find(ui.rating).elements.pop()
        rating.value = 5
        rating.update()
        assert item.priority == 5


# ---------------------------------------------------------------------------
# ModelForm — ui.radio widget
# ---------------------------------------------------------------------------

class Choice(pydantic.BaseModel):
    # Literal auto-infers select_options; widget_type override picks them up as radio/toggle options
    color: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.radio')] = 'green'
    color_toggle: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.toggle')] = 'green'


class ColorItem(pydantic.BaseModel):
    bg: Annotated[str, niceview.Field(widget_type='ui.color_input', label='Background', color_preview=True)] = '#ffffff'


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


class TestModelFormColorInputWidget:
    async def test_color_input_widget_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(ColorItem()).render()

        await user.open('/')
        await user.should_see(ui.color_input)

    async def test_color_input_initial_value_in_model(self, user: User) -> None:
        item = ColorItem(bg='#123456')

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        assert item.bg == '#123456'


class TestModelFormToggleWidget:
    async def test_toggle_widget_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(Choice()).render()

        await user.open('/')
        await user.should_see(ui.toggle)

    async def test_toggle_initial_value_in_model(self, user: User) -> None:
        item = Choice(color_toggle='red')

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        await user.should_see(ui.toggle)
        assert item.color_toggle == 'red'


# ---------------------------------------------------------------------------
# Profiles (Meta.profiles)
# ---------------------------------------------------------------------------

class ProfiledPerson(pydantic.BaseModel):
    name: str = pydantic.Field(default='', title='Name')
    age: int = pydantic.Field(default=0, title='Age')
    active: bool = pydantic.Field(default=True, title='Active')

    class Meta:
        profiles = {
            'summary': ['name'],
            'detail': '__all__',
        }


class Backend(enum.Enum):
    PROMETHEUS = 1
    INFLUX2 = 2
    SQL = 3


class TelemetryConfig(pydantic.BaseModel):
    name: str = pydantic.Field(default='', title='Name')
    backend: Backend = pydantic.Field(default=Backend.PROMETHEUS, title='Backend')


class TestModelFormEnumWidget:
    async def test_enum_renders_as_select(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(TelemetryConfig()).render()

        await user.open('/')
        await user.should_see(ui.select)

    async def test_enum_initial_value_displayed(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(TelemetryConfig(backend=Backend.INFLUX2))
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].item.backend == Backend.INFLUX2

    async def test_enum_change_updates_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(TelemetryConfig())
            form.render()
            captured.append(form)

        await user.open('/')
        captured[0].widgets['backend'].set_value(Backend.SQL)
        assert captured[0].item.backend == Backend.SQL

    async def test_enum_select_options_are_enum_members(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(TelemetryConfig())
            form.render()
            captured.append(form)

        await user.open('/')
        options = captured[0].widgets['backend'].options
        assert Backend.PROMETHEUS in options
        assert Backend.INFLUX2 in options
        assert Backend.SQL in options


class TestModelFormProfiles:
    async def test_summary_profile_shows_only_name(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(ProfiledPerson(), profile='summary').render()

        await user.open('/')
        await user.should_see('Name')
        await user.should_not_see(ui.number)

    async def test_detail_profile_shows_all_fields(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(ProfiledPerson(), profile='detail').render()

        await user.open('/')
        await user.should_see('Name')
        await user.should_see(ui.number)
        await user.should_see(ui.switch)

    async def test_unknown_profile_raises(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="unknown_profile"):
            ModelForm(ProfiledPerson, profile='unknown_profile')

    async def test_grid_with_profile(self, user: User) -> None:
        items = [ProfiledPerson(name='Alice')]

        @ui.page('/')
        def page():
            ModelGrid.from_list(ProfiledPerson, items, profile='summary').render()

        await user.open('/')
        await user.should_see(ui.aggrid)


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
            EditGridWrapper.from_list(Person, [], title='People')

        await user.open('/')
        await user.should_see('People')

    async def test_add_button_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Person, [])

        await user.open('/')
        await user.should_see(ui.button, content='add')

    async def test_delete_button_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Person, [])

        await user.open('/')
        await user.should_see(ui.button, content='delete')

    async def test_grid_element_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Person, [])

        await user.open('/')
        await user.should_see(ui.aggrid)
