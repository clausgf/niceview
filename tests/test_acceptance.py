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
import asyncio
import datetime
import enum
import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User
from typing import Annotated, Callable, Literal, Optional

from niceview.util import confirm_dialog, input_dialog

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
            EditFormWrapper.from_item(Person(), title='Edit Person').render()

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
    volume: Annotated[int, pydantic.Field(default=50, ge=0, le=100, title='Volume'), niceview.Field(widget_type='ui.slider')]
    priority: Annotated[int, pydantic.Field(default=3, ge=1, le=5, title='Priority'), niceview.Field(widget_type='ui.rating')]


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
    color_inline: Annotated[Literal['red', 'green', 'blue'], niceview.Field(widget_type='ui.radio', props='inline')] = 'green'


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

    async def test_radio_inline_prop_sets_horizontal_layout(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Choice())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['color_inline'].props.get('inline') is not None


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
            EditGridWrapper.from_list(Person, [], title='People').render()

        await user.open('/')
        await user.should_see('People')

    async def test_add_button_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Person, []).render()

        await user.open('/')
        await user.should_see(ui.button, content='add')

    async def test_delete_button_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Person, []).render()

        await user.open('/')
        await user.should_see(ui.button, content='delete')

    async def test_grid_element_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Person, []).render()

        await user.open('/')
        await user.should_see(ui.aggrid)


# ---------------------------------------------------------------------------
# render_field / render_nonfield_errors
# ---------------------------------------------------------------------------

class TestRenderField:
    async def test_single_field_renders_widget(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            form.render_field('name')
            captured.append(form)

        await user.open('/')
        assert 'name' in captured[0].widgets
        await user.should_see('Name')

    async def test_other_fields_not_rendered(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            form.render_field('name')
            captured.append(form)

        await user.open('/')
        assert 'age' not in captured[0].widgets
        assert 'active' not in captured[0].widgets

    async def test_multiple_render_field_calls_accumulate(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            form.render_field('name')
            form.render_field('age')
            captured.append(form)

        await user.open('/')
        assert 'name' in captured[0].widgets
        assert 'age' in captured[0].widgets
        assert 'active' not in captured[0].widgets

    async def test_render_field_unknown_raises(self, user: User) -> None:
        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            with pytest.raises(ValueError, match="not in the form"):
                form.render_field('nonexistent')

        await user.open('/')

    async def test_render_field_widget_wired_to_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person(name='Alice'))
            form.render_field('name')
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['name'].value == 'Alice'

    async def test_render_nonfield_errors_creates_element(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            form.render_field('name')
            form.render_nonfield_errors()
            captured.append(form)

        await user.open('/')
        assert captured[0]._nonfield_error_element is not None

    async def test_render_field_returns_widget(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            widget = form.render_field('name')
            captured.append((form, widget))

        await user.open('/')
        form, widget = captured[0]
        assert widget is form.widgets['name']

    async def test_render_nonfield_errors_returns_label(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            form.render_field('name')
            label = form.render_nonfield_errors()
            captured.append((form, label))

        await user.open('/')
        form, label = captured[0]
        assert label is form._nonfield_error_element

    async def test_render_field_label_override(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(Person()).render_field('name', label='Kurzname')

        await user.open('/')
        await user.should_see('Kurzname')
        await user.should_not_see('Name')

    async def test_render_field_label_empty(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Person())
            form.render_field('name', label='')
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['name'].label == ''
        await user.should_not_see('Name')


# ---------------------------------------------------------------------------
# ModelForm — datetime / time widget precision and None handling
# ---------------------------------------------------------------------------

_DT_WITH_MICROSECONDS = datetime.datetime(2026, 7, 4, 14, 23, 45, 783421, tzinfo=datetime.timezone.utc)
_TIME_WITH_MICROSECONDS = datetime.time(9, 30, 15, 500000)
_DATE_VALUE = datetime.date(2026, 7, 4)


class _EventModel(pydantic.BaseModel):
    start: datetime.datetime = pydantic.Field(
        default_factory=lambda: _DT_WITH_MICROSECONDS, title='Start'
    )


class _AlarmModel(pydantic.BaseModel):
    ring: datetime.time = pydantic.Field(
        default=_TIME_WITH_MICROSECONDS, title='Ring'
    )


class _AppointmentModel(pydantic.BaseModel):
    day: Optional[datetime.date] = pydantic.Field(default=None, title='Day')
    start: Optional[datetime.datetime] = pydantic.Field(default=None, title='Start')
    alarm: Optional[datetime.time] = pydantic.Field(default=None, title='Alarm')


class _PermsModel(pydantic.BaseModel):
    perms: list[Literal['read', 'write', 'admin']] = []


class _OptPermsModel(pydantic.BaseModel):
    perms: Optional[list[Literal['read', 'write', 'admin']]] = None


class _ConstrainedTagsModel(pydantic.BaseModel):
    tags: list[Annotated[str, pydantic.Field(pattern=r'^[a-z]+$', min_length=2, max_length=10)]] = []


class _CheckboxPermsModel(pydantic.BaseModel):
    perms: Annotated[list[Literal['read', 'write', 'admin']], niceview.Field(widget_type='checkbox_group')] = []


class _CheckboxPermsInlineModel(pydantic.BaseModel):
    perms: Annotated[
        list[Literal['read', 'write', 'admin']],
        niceview.Field(widget_type='checkbox_group', props='inline'),
    ] = []


class _OptCheckboxPermsModel(pydantic.BaseModel):
    perms: Annotated[
        Optional[list[Literal['read', 'write', 'admin']]],
        niceview.Field(widget_type='checkbox_group'),
    ] = None


class TestModelFormMultiSelectWidget:
    async def test_multiple_flag_on_widget(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_PermsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['perms'].props.get('multiple') is not None

    async def test_options_available(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_PermsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['perms'].options == ['read', 'write', 'admin']

    async def test_initial_list_value_loads(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_PermsModel(perms=['read', 'admin']))
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['perms'].value == ['read', 'admin']

    async def test_selection_written_to_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_PermsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['perms'].value = ['write', 'admin']
        form._from_widget_value_to_current_item('perms')
        assert form._current_item.perms == ['write', 'admin']

    async def test_none_loads_as_empty_list(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_OptPermsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['perms'].value == []

    async def test_empty_selection_sets_none_on_optional_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_OptPermsModel(perms=['read']))
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['perms'].value = []
        form._from_widget_value_to_current_item('perms')
        assert form._current_item.perms is None

    async def test_empty_selection_stays_list_on_required_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_PermsModel(perms=['read']))
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['perms'].value = []
        form._from_widget_value_to_current_item('perms')
        assert form._current_item.perms == []


class TestModelFormConstrainedChipsWidget:
    async def test_renders_as_input_chips(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(_ConstrainedTagsModel()).render()

        await user.open('/')
        await user.should_see(ui.input_chips)

    async def test_valid_tags_no_error(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_ConstrainedTagsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['tags'].value = ['ok', 'go']
        form._from_widget_value_to_current_item('tags')
        assert form._current_item.tags == ['ok', 'go']
        form._validate()
        assert not form.has_validation_errors

    async def test_pattern_violation_sets_field_error(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_ConstrainedTagsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['tags'].value = ['BAD1']
        form._from_widget_value_to_current_item('tags')
        form._validate()
        assert 'tags' in form.validation_errors

    async def test_min_length_violation_sets_field_error(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_ConstrainedTagsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['tags'].value = ['a']
        form._from_widget_value_to_current_item('tags')
        form._validate()
        assert 'tags' in form.validation_errors


class TestModelFormCheckboxGroupWidget:
    async def test_renders_a_checkbox_per_option(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelForm.from_item(_CheckboxPermsModel()).render()

        await user.open('/')
        await user.should_see('read')
        await user.should_see('write')
        await user.should_see('admin')

    async def test_default_layout_is_column(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_CheckboxPermsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        assert isinstance(captured[0].widgets['perms'].widget, ui.column)

    async def test_inline_prop_gives_row_layout(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_CheckboxPermsInlineModel())
            form.render()
            captured.append(form)

        await user.open('/')
        assert isinstance(captured[0].widgets['perms'].widget, ui.row)

    async def test_initial_list_value_checks_boxes(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_CheckboxPermsModel(perms=['read', 'admin']))
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['perms'].value == ['read', 'admin']

    async def test_checking_a_box_updates_model(self, user: User) -> None:
        item = _CheckboxPermsModel()

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        user.find('write').click()
        assert item.perms == ['write']

    async def test_unchecking_a_box_updates_model(self, user: User) -> None:
        item = _CheckboxPermsModel(perms=['read', 'write'])

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        user.find('write').click()
        assert item.perms == ['read']

    async def test_none_loads_as_empty_selection(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_OptCheckboxPermsModel())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].widgets['perms'].value == []

    async def test_unchecking_last_box_sets_none_on_optional_model(self, user: User) -> None:
        item = _OptCheckboxPermsModel(perms=['read'])

        @ui.page('/')
        def page():
            ModelForm.from_item(item).render()

        await user.open('/')
        user.find('read').click()
        assert item.perms is None


class TestModelFormDatetimeWidget:
    async def test_datetime_microseconds_truncated_in_widget(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_EventModel())
            form.render()
            captured.append(form)

        await user.open('/')
        value = captured[0].widgets['start'].value
        assert '.' not in value, f"Widget value contains sub-seconds: {value!r}"
        assert value == '2026-07-04T14:23:45'

    async def test_time_microseconds_truncated_in_widget(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_AlarmModel())
            form.render()
            captured.append(form)

        await user.open('/')
        value = captured[0].widgets['ring'].value
        assert '.' not in value, f"Widget value contains sub-seconds: {value!r}"
        assert value == '09:30:15'

    async def test_none_datetime_loads_as_empty_widget(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_AppointmentModel())
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        assert form.widgets['start'].value == ''
        assert form.widgets['alarm'].value == ''
        assert form.widgets['day'].value == ''

    async def test_empty_datetime_widget_sets_none_on_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_EventModel())
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['start'].value = ''
        form._from_widget_value_to_current_item('start')
        assert form._current_item.start is None

    async def test_empty_time_widget_sets_none_on_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_AlarmModel())
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['ring'].value = ''
        form._from_widget_value_to_current_item('ring')
        assert form._current_item.ring is None

    async def test_date_widget_parses_string_to_date(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_AppointmentModel(day=_DATE_VALUE))
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        assert form.widgets['day'].value == '2026-07-04'
        form._from_widget_value_to_current_item('day')
        assert form._current_item.day == _DATE_VALUE

    async def test_empty_date_widget_sets_none_on_model(self, user: User) -> None:
        captured = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(_AppointmentModel(day=_DATE_VALUE))
            form.render()
            captured.append(form)

        await user.open('/')
        form = captured[0]
        form.widgets['day'].value = ''
        form._from_widget_value_to_current_item('day')
        assert form._current_item.day is None


# ---------------------------------------------------------------------------
# confirm_dialog / input_dialog
# Dialog functions are triggered by a button click (not awaited in the page
# handler directly) because NiceGUI's User fixture requires the page handler
# to return before page setup completes.
# ---------------------------------------------------------------------------

class TestConfirmDialog:
    async def test_ok_returns_true(self, user: User) -> None:
        results: list[bool] = []

        @ui.page('/')
        def page():
            async def show():
                results.append(await confirm_dialog('Delete Device', 'Irreversible.'))
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Delete Device')
        await user.should_see('Irreversible.')
        user.find('OK').click()
        await asyncio.sleep(0.1)
        assert results == [True]

    async def test_cancel_returns_false(self, user: User) -> None:
        results: list[bool] = []

        @ui.page('/')
        def page():
            async def show():
                results.append(await confirm_dialog('Title', 'Msg'))
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Msg')  # wait for dialog
        user.find('Cancel').click()
        await asyncio.sleep(0.1)
        assert results == [False]

    async def test_custom_labels(self, user: User) -> None:
        @ui.page('/')
        def page():
            async def show():
                await confirm_dialog('Title', 'Msg', ok_label='Delete', cancel_label='Abort')
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Delete')
        await user.should_see('Abort')


class TestInputDialog:
    async def test_ok_returns_entered_value(self, user: User) -> None:
        results: list = []

        @ui.page('/')
        def page():
            async def show():
                results.append(await input_dialog('Create Project', label='Project Name'))
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Project Name')
        user.find('Project Name').type('hello')
        user.find('OK').click()
        await asyncio.sleep(0.1)
        assert results == ['hello']

    async def test_cancel_returns_none(self, user: User) -> None:
        results: list = []

        @ui.page('/')
        def page():
            async def show():
                results.append(await input_dialog('Title', label='Name'))
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Name')  # wait for dialog
        user.find('Cancel').click()
        await asyncio.sleep(0.1)
        assert results == [None]

    async def test_validator_blocks_invalid_input(self, user: User) -> None:
        results: list = []

        @ui.page('/')
        def page():
            async def show():
                results.append(await input_dialog(
                    'Title', label='Name',
                    validator=lambda v: v.isalpha(),
                    error_message='Letters only',
                ))
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Name')  # wait for dialog
        user.find('Name').type('123')
        user.find('OK').click()
        await asyncio.sleep(0.1)
        assert results == []  # validator blocked submission

    async def test_validator_accepts_valid_input(self, user: User) -> None:
        results: list = []

        @ui.page('/')
        def page():
            async def show():
                results.append(await input_dialog(
                    'Title', label='Name',
                    validator=lambda v: v.isalpha(),
                ))
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Name')  # wait for dialog
        user.find('Name').type('hello')
        user.find('OK').click()
        await asyncio.sleep(0.1)
        assert results == ['hello']
