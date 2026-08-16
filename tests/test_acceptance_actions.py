"""
Acceptance tests for form actions: buttons that are not fields.

The notation is '@name' in the layout plus an `actions` table; every wrapper takes the same
FormAction into its title row as `chrome_actions`. What is checked here is what it renders and
what a click does.
"""
import asyncio
from pathlib import Path

import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User

from niceview import DrillDownWrapper, EditFormWrapper, EditGridWrapper, FormAction, ModelForm
from niceview.dataadapter import ListAdapter
from niceview.style import ChromeStyle


class Connection(pydantic.BaseModel):
    host: str = 'localhost'
    port: int = 8080
    password: str = 'secret'


class Pair(pydantic.BaseModel):
    """A model that can be made invalid without leaving a field empty."""
    first: str = 'a'
    second: str = 'b'

    @pydantic.model_validator(mode='after')
    def different(self):
        if self.first == self.second:
            raise ValueError('first and second must differ')
        return self


def _form(build) -> list:
    captured: list = []

    @ui.page('/')
    def page():
        captured.append(build())

    return captured


def _parent(widget) -> ui.element:
    return widget.parent_slot.parent


def _buttons(container: ui.element) -> list:
    return [child for child in container.default_slot.children if isinstance(child, ui.button)]


class TestPlacement:
    async def test_an_action_sits_where_the_layout_puts_it(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Connection(),
            layout=['host', ['port', '@test']],
            actions={'test': FormAction('Test', icon='bolt')},
        ).render())
        await user.open('/')
        form = captured[0]

        button = form.action_buttons['test']
        assert isinstance(button, ui.button)
        assert _parent(button) is _parent(form.w('port'))
        await user.should_see('Test')

    async def test_w_addresses_an_action_as_the_layout_writes_it(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        form = captured[0]
        assert form.w('@test') is form.action_buttons['test']
        assert form.w('@test', ui.button) is form.action_buttons['test']

    async def test_an_action_is_not_a_field(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        form = captured[0]
        assert 'test' not in form.widgets and '@test' not in form.widgets
        assert list(form._fields.field_names) == ['host']

    async def test_render_action_places_one_by_hand(self, user: User) -> None:
        def build():
            form = ModelForm.from_item(Connection(), actions={'test': FormAction('Test')})
            with ui.row() as row:
                form.render_field('host')
                form.render_action('test')
            return form, row

        captured = _form(build)
        await user.open('/')
        form, row = captured[0]
        assert _parent(form.w('@test')) is row

    async def test_render_action_accepts_the_layout_spelling(self, user: User) -> None:
        def build():
            form = ModelForm.from_item(Connection(), actions={'test': FormAction('Test')})
            form.render_action('@test')
            return form

        captured = _form(build)
        await user.open('/')
        assert isinstance(captured[0].w('@test'), ui.button)


class TestClicks:
    async def test_a_click_reaches_the_callback_with_the_form(self, user: User) -> None:
        seen: list = []

        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('Test', on_click=lambda e: seen.append(e))},
        ).render())
        await user.open('/')
        user.find('Test').click()
        await user.should_see('Test')

        assert len(seen) == 1
        event = seen[0]
        assert event.form is captured[0]
        assert event.name == 'test'
        assert event.action.label == 'Test'
        assert event.form.item.host == 'localhost'

    async def test_the_callback_sees_what_the_widgets_hold(self, user: User) -> None:
        seen: list = []

        _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('Test', on_click=lambda e: seen.append(e.form.draft.host))},
        ).render())
        await user.open('/')
        user.find('Host').clear().type('example.org').trigger('blur')
        user.find('Test').click()
        await user.should_see('Test')
        assert seen == ['example.org']

    async def test_an_action_without_a_callback_is_inert(self, user: User) -> None:
        _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        user.find('Test').click()
        await user.should_see('Test')


class TestRequiresValid:
    async def test_disabled_while_the_form_is_invalid(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Pair(), layout=['first', 'second', '@go'],
            actions={'go': FormAction('Go', requires_valid=True)},
        ).render())
        await user.open('/')
        button = captured[0].w('@go')
        assert button.enabled is True

        user.find('First').clear().type('b').trigger('blur')
        await user.should_see('first and second must differ')
        assert button.enabled is False

        user.find('First').clear().type('c').trigger('blur')
        await user.should_see('Go')
        assert button.enabled is True

    async def test_disabled_from_the_start_when_the_item_is_invalid(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Pair.model_construct(first='x', second='x'), layout=['first', '@go'],
            actions={'go': FormAction('Go', requires_valid=True)},
        ).render())
        await user.open('/')
        assert captured[0].w('@go').enabled is False

    async def test_an_action_without_the_flag_stays_enabled(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Pair.model_construct(first='x', second='x'), layout=['first', '@go'],
            actions={'go': FormAction('Go')},
        ).render())
        await user.open('/')
        assert captured[0].w('@go').enabled is True


class TestStyling:
    async def test_the_place_applies_but_no_role(self, user: User) -> None:
        # An action sits among the fields, so it takes the 'form' place — but it is none of
        # niceview's roles and brings its own props instead.
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('Test', props='color=primary')},
            chrome_style=ChromeStyle(form_button_props='flat'),
        ).render())
        await user.open('/')
        button = captured[0].w('@test')
        assert button._props.get('flat') is True
        assert button._props.get('color') == 'primary'

    async def test_layout_classes_win_over_the_actions_own(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=[['host', '@test:w-1/4']],
            actions={'test': FormAction('Test', classes='w-full')},
        ).render())
        await user.open('/')
        classes = captured[0].w('@test')._classes
        assert 'w-1/4' in classes and 'w-full' not in classes

    async def test_in_a_row_an_action_sits_on_the_field_box(self, user: User) -> None:
        # Centred over the field *box*, not over the 20px Quasar keeps free below it for the
        # error message — 'mb-5' takes that half-of-20px offset back out.
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=[['host', '@test']],
            actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        classes = captured[0].w('@test')._classes
        assert 'self-center' in classes and 'mb-5' in classes

    async def test_a_row_of_switches_reserves_nothing_to_compensate(self, user: User) -> None:
        class Flags(pydantic.BaseModel):
            enabled: bool = True
            verbose: bool = False

        captured = _form(lambda: ModelForm.from_item(
            Flags(), layout=[['enabled', '@test']],
            actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        classes = captured[0].w('@test')._classes
        assert 'self-center' in classes and 'mb-5' not in classes

    async def test_one_field_with_a_strip_is_enough(self, user: User) -> None:
        class Mixed(pydantic.BaseModel):
            enabled: bool = True
            host: str = 'localhost'

        captured = _form(lambda: ModelForm.from_item(
            Mixed(), layout=[['enabled', 'host', '@test']],
            actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        assert 'mb-5' in captured[0].w('@test')._classes

    async def test_a_row_of_actions_alone_compensates_nothing(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', ['@test', '@more']],
            actions={'test': FormAction('Test'), 'more': FormAction('More')},
        ).render())
        await user.open('/')
        assert 'mb-5' not in captured[0].w('@test')._classes

    async def test_outside_a_row_an_action_brings_no_classes(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        assert captured[0].w('@test')._classes == []

    async def test_the_tooltip_is_the_actions_own(self, user: User) -> None:
        captured = _form(lambda: ModelForm.from_item(
            Connection(), layout=['host', '@test'],
            actions={'test': FormAction('', icon='bolt', tooltip='Test the connection')},
        ).render())
        await user.open('/')
        button = captured[0].w('@test')
        assert any(isinstance(c, ui.tooltip) for c in button.default_slot.children)


class TestWrapperActions:
    async def test_an_action_joins_the_title_row(self, user: User) -> None:
        captured = _form(lambda: EditFormWrapper.from_item(
            Connection(), title='Connection',
            chrome_actions={'test': FormAction('Test', icon='bolt')},
        ).render())
        await user.open('/')
        wrapper = captured[0]

        button = wrapper.action_buttons['test']
        assert _parent(_parent(button)) is wrapper.title_row
        await user.should_see('Test')

    async def test_the_applications_action_comes_first(self, user: User, tmp_path: Path) -> None:
        captured = _form(lambda: EditFormWrapper.from_json(
            Connection, tmp_path / 'conn.json', title='Connection',
            chrome_actions={'test': FormAction('Test')},
        ).render())
        await user.open('/')
        wrapper = captured[0]

        # Save and Refresh keep the right edge they have in every other wrapper.
        order = _buttons(_parent(wrapper.action_buttons['test']))
        assert order[0] is wrapper.action_buttons['test']
        assert order[1] is wrapper.refresh_button
        assert order[2] is wrapper.save_button

    async def test_requires_valid_reaches_the_title_row(self, user: User) -> None:
        captured = _form(lambda: EditFormWrapper.from_item(
            Pair(), title='Pair',
            chrome_actions={'go': FormAction('Go', requires_valid=True)},
        ).render())
        await user.open('/')
        button = captured[0].action_buttons['go']
        assert button.enabled is True

        user.find('First').clear().type('b').trigger('blur')
        await user.should_see('first and second must differ')
        assert button.enabled is False

    async def test_a_click_reaches_the_callback(self, user: User) -> None:
        seen: list = []
        captured = _form(lambda: EditFormWrapper.from_item(
            Connection(), title='Connection',
            chrome_actions={'test': FormAction('Test', on_click=lambda e: seen.append(e))},
        ).render())
        await user.open('/')
        user.find('Test').click()
        await user.should_see('Test')
        assert seen[0].form is captured[0].form

    async def test_both_halves_at_once(self, user: User) -> None:
        captured = _form(lambda: EditFormWrapper.from_item(
            Connection(), title='Connection',
            layout=['host', '@test'],
            actions={'test': FormAction('Test field')},
            chrome_actions={'all': FormAction('Test all')},
        ).render())
        await user.open('/')
        wrapper = captured[0]
        assert 'all' in wrapper.action_buttons and 'test' not in wrapper.action_buttons
        assert 'test' in wrapper.form.action_buttons


class TestErrors:
    def test_an_action_needs_a_label_or_an_icon(self) -> None:
        with pytest.raises(ValueError, match='needs a label or an icon'):
            FormAction()

    def test_an_undeclared_action_names_its_position(self) -> None:
        with pytest.raises(ValueError, match=r"layout\[1\]: unknown action 'test'"):
            ModelForm.from_item(Connection(), layout=['host', '@test'])

    def test_the_action_table_holds_form_actions(self) -> None:
        with pytest.raises(TypeError, match='must be a FormAction'):
            ModelForm.from_item(Connection(), layout=['host', '@test'], actions={'test': 'Test'})

    def test_the_name_carries_no_at_sign(self) -> None:
        with pytest.raises(ValueError, match='Invalid action name'):
            ModelForm.from_item(Connection(), layout=['host', '@test'],
                                actions={'@test': FormAction('Test')})

    def test_render_action_rejects_an_unknown_name(self) -> None:
        form = ModelForm.from_item(Connection(), actions={'test': FormAction('Test')})
        with pytest.raises(ValueError, match="Unknown action 'nope'"):
            form.render_action('nope')


def _selection(row_key: str | None):
    """
    Stand in for the browser's answer to 'which row is selected?'.

    A grid selection cannot be made in the User fixture — the AG Grid lives in the client — so
    the tests replace the one await that asks for it and drive the rest of the real click path.
    """
    async def get_selected_row_key() -> str | None:
        return row_key
    return get_selected_row_key


class TestGridWrapperActions:
    """EditGridWrapper's title row: the same FormAction, answered with the selection."""

    async def test_an_action_joins_the_title_row(self, user: User) -> None:
        captured = _form(lambda: EditGridWrapper.from_list(
            Connection, [Connection()], title='Connections',
            chrome_actions={'export': FormAction('Export', icon='download')},
        ).render())
        await user.open('/')
        wrapper = captured[0]

        button = wrapper.action_buttons['export']
        assert _parent(_parent(button)) is wrapper.title_row
        await user.should_see('Export')

    async def test_the_applications_action_comes_first(self, user: User) -> None:
        captured = _form(lambda: EditGridWrapper.from_list(
            Connection, [Connection()], title='Connections',
            chrome_actions={'export': FormAction('Export')},
        ).render())
        await user.open('/')
        wrapper = captured[0]

        # niceview's own buttons keep the right edge they have in every other wrapper.
        order = _buttons(_parent(wrapper.action_buttons['export']))
        assert order[0] is wrapper.action_buttons['export']
        assert order[1] is wrapper.refresh_button

    async def test_a_click_carries_the_selected_row(self, user: User) -> None:
        seen: list = []
        items = [Connection(host='alpha'), Connection(host='beta')]
        captured = _form(lambda: EditGridWrapper.from_list(
            Connection, items, title='Connections',
            chrome_actions={'ping': FormAction('Ping', on_click=lambda e: seen.append(e))},
        ).render())
        await user.open('/')
        wrapper = captured[0]
        key = wrapper.grid.adapter.key_from_item(items[1])
        wrapper._get_selected_row_key = _selection(key)

        user.find('Ping').click()
        await asyncio.sleep(0.1)  # a grid's action asks the client for the selection first
        assert seen[0].row_key == key
        assert seen[0].item.host == 'beta'
        assert seen[0].wrapper is wrapper
        assert seen[0].name == 'ping'

    async def test_a_click_without_a_selection_says_so(self, user: User) -> None:
        seen: list = []
        captured = _form(lambda: EditGridWrapper.from_list(
            Connection, [Connection()], title='Connections',
            chrome_actions={'ping': FormAction('Ping', on_click=lambda e: seen.append(e))},
        ).render())
        await user.open('/')
        captured[0]._get_selected_row_key = _selection(None)

        user.find('Ping').click()
        await asyncio.sleep(0.1)  # a grid's action asks the client for the selection first
        assert seen[0].row_key is None and seen[0].item is None

    def test_requires_valid_is_refused_without_a_form(self) -> None:
        with pytest.raises(ValueError, match='requires_valid needs a form'):
            EditGridWrapper.from_list(Connection, [], chrome_actions={'go': FormAction('Go', requires_valid=True)})


class TestDrillDownWrapperActions:
    """DrillDownWrapper's title row: the actions belong to the detail view, left of Delete."""

    async def test_an_action_is_hidden_in_the_list_view(self, user: User) -> None:
        captured = _form(lambda: DrillDownWrapper.from_list(
            Connection, [Connection()], list_title='Connections',
            chrome_actions={'ping': FormAction('Ping')},
        ).render())
        await user.open('/')
        assert captured[0].action_buttons['ping'].visible is False

    async def test_an_action_shows_in_the_detail_view(self, user: User) -> None:
        items = [Connection(host='alpha')]
        adapter = ListAdapter(Connection, items)
        key = adapter.key_from_item(items[0])
        captured = _form(lambda: DrillDownWrapper.from_adapter(
            Connection, adapter, chrome_actions={'ping': FormAction('Ping')},
        ).render().open(key))
        await user.open('/')

        assert captured[0].action_buttons['ping'].visible is True
        await user.should_see('Ping')

    async def test_the_applications_actions_sit_left_of_delete(self, user: User) -> None:
        items = [Connection(host='alpha')]
        adapter = ListAdapter(Connection, items)
        key = adapter.key_from_item(items[0])
        captured = _form(lambda: DrillDownWrapper.from_adapter(
            Connection, adapter, chrome_actions={'ping': FormAction('Ping')},
        ).render().open(key))
        await user.open('/')
        wrapper = captured[0]

        order = _buttons(_parent(wrapper.action_buttons['ping']))
        assert order[0] is wrapper.action_buttons['ping']
        assert order[-1] is wrapper.delete_button

    async def test_a_click_names_the_item_on_screen(self, user: User) -> None:
        seen: list = []
        items = [Connection(host='alpha'), Connection(host='beta')]
        adapter = ListAdapter(Connection, items)
        key = adapter.key_from_item(items[1])
        captured = _form(lambda: DrillDownWrapper.from_adapter(
            Connection, adapter,
            chrome_actions={'ping': FormAction('Ping', on_click=lambda e: seen.append(e))},
        ).render().open(key))
        await user.open('/')

        user.find('Ping').click()
        await user.should_see('Ping')
        assert seen[0].key == key
        assert seen[0].item.host == 'beta'
        assert seen[0].wrapper is captured[0]

    async def test_requires_valid_follows_the_detail_form(self, user: User) -> None:
        items = [Pair()]
        adapter = ListAdapter(Pair, items)
        key = adapter.key_from_item(items[0])
        captured = _form(lambda: DrillDownWrapper.from_adapter(
            Pair, adapter, chrome_actions={'go': FormAction('Go', requires_valid=True)},
        ).render().open(key))
        await user.open('/')
        button = captured[0].action_buttons['go']
        assert button.enabled is True

        user.find('First').clear().type('b').trigger('blur')
        await user.should_see('first and second must differ')
        assert button.enabled is False

    def test_requires_valid_is_refused_with_a_detail_view_of_your_own(self) -> None:
        with pytest.raises(ValueError, match='requires_valid needs a form'):
            DrillDownWrapper.from_list(Connection, [], render_detail=lambda adapter, key, set_key: None,
                                       chrome_actions={'go': FormAction('Go', requires_valid=True)})
