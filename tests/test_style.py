"""
Tests for the chrome styling shared by EditGridWrapper, EditFormWrapper and DrillDownWrapper:
the ChromeStyle value object, the application-wide default, and the per-wrapper override.
"""
import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User

from niceview.drilldown import DrillDownWrapper
from niceview.editwrapper import EditFormWrapper, EditGridWrapper
from niceview.modellist import ModelList
from niceview.style import ChromeStyle, get_chrome_style, set_chrome_style


class Contact(pydantic.BaseModel):
    name: str = pydantic.Field(default='', title='Name')
    email: str = pydantic.Field(default='', title='Email')


@pytest.fixture(autouse=True)
def restore_chrome_style():
    """The chrome style is application-wide state — put it back after every test."""
    original = get_chrome_style()
    yield
    set_chrome_style(original)


def _buttons(client) -> list[ui.button]:
    return [e for e in client.layout.descendants() if isinstance(e, ui.button)]


def _tooltips(client) -> list[ui.tooltip]:
    return [e for e in client.layout.descendants() if isinstance(e, ui.tooltip)]


# ---------------------------------------------------------------------------
# ChromeStyle
# ---------------------------------------------------------------------------

class TestChromeStyle:
    def test_replace_returns_a_copy(self):
        style = ChromeStyle()
        derived = style.replace(button_props='dense')
        assert derived.button_props == 'dense'
        assert style.button_props == 'dense flat'  # the original is untouched

    def test_replace_keeps_the_other_attributes(self):
        derived = ChromeStyle(title_classes='text-h5 grow').replace(tooltips=False)
        assert derived.title_classes == 'text-h5 grow'
        assert derived.tooltips is False

    def test_replace_rejects_unknown_attributes(self):
        with pytest.raises(TypeError):
            ChromeStyle().replace(no_such_attribute='x')

    def test_set_chrome_style_with_keywords_changes_only_those(self):
        set_chrome_style(button_props='dense')
        assert get_chrome_style().button_props == 'dense'
        assert get_chrome_style().title_classes == ChromeStyle().title_classes

    def test_set_chrome_style_with_an_instance_replaces_wholesale(self):
        set_chrome_style(ChromeStyle(button_props='outline'))
        assert get_chrome_style().button_props == 'outline'

    def test_set_chrome_style_returns_the_new_style(self):
        assert set_chrome_style(tooltips=False) is get_chrome_style()


# ---------------------------------------------------------------------------
# The application-wide default reaches every wrapper
# ---------------------------------------------------------------------------

class TestGlobalChromeStyle:
    async def test_grid_wrapper_buttons_use_the_global_props(self, user: User) -> None:
        set_chrome_style(button_props='outline')

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, []).render()

        await user.open('/')
        with user._client:
            assert all(b.props.get('outline') for b in _buttons(user.client))

    async def test_form_wrapper_buttons_use_the_global_props(self, user: User, tmp_path) -> None:
        set_chrome_style(button_props='outline')

        @ui.page('/')
        def page():
            EditFormWrapper.from_json(Contact, tmp_path / 'contact.json').render()

        await user.open('/')
        with user._client:
            assert all(b.props.get('outline') for b in _buttons(user.client))

    async def test_drilldown_buttons_use_the_global_props(self, user: User) -> None:
        set_chrome_style(button_props='outline')

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, []).render()

        await user.open('/')
        with user._client:
            assert all(b.props.get('outline') for b in _buttons(user.client))

    async def test_tooltips_can_be_turned_off_globally(self, user: User) -> None:
        set_chrome_style(tooltips=False)

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, []).render()

        await user.open('/')
        with user._client:
            assert _tooltips(user.client) == []


# ---------------------------------------------------------------------------
# The per-wrapper override
# ---------------------------------------------------------------------------

class TestChromeStyleOption:
    async def test_wrapper_option_wins_over_the_global_default(self, user: User) -> None:
        set_chrome_style(button_props='outline')

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], chrome_style=ChromeStyle(button_props='push')).render()

        await user.open('/')
        with user._client:
            buttons = _buttons(user.client)
            assert buttons and all(b.props.get('push') and not b.props.get('outline') for b in buttons)

    async def test_title_classes_reach_the_title_label(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='People',
                                      chrome_style=get_chrome_style().replace(title_classes='text-h4')).render()

        await user.open('/')
        with user._client:
            labels = [e for e in user.client.layout.descendants()
                      if isinstance(e, ui.label) and e.text == 'People']
            assert labels and 'text-h4' in labels[0].classes

    async def test_drilldown_takes_the_option_too(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], chrome_style=ChromeStyle(tooltips=False)).render()

        await user.open('/')
        with user._client:
            assert _tooltips(user.client) == []


# ---------------------------------------------------------------------------
# The three title rows agree
# ---------------------------------------------------------------------------

class TestChromeConsistency:
    async def test_drilldown_buttons_carry_tooltips(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], list_title='Contacts').render()

        await user.open('/')
        with user._client:
            assert 'Add a new item' in [t.text for t in _tooltips(user.client)]

    async def test_the_two_add_buttons_look_the_same(self, user: User) -> None:
        buttons: dict[str, ui.button] = {}

        @ui.page('/')
        def page():
            buttons['grid'] = EditGridWrapper.from_list(Contact, [], title='Grid').render().add_button
            buttons['drilldown'] = DrillDownWrapper.from_list(Contact, [], list_title='List').render().add_button

        await user.open('/')
        assert dict(buttons['grid'].props) == dict(buttons['drilldown'].props)

    async def test_all_three_title_rows_share_their_classes(self, user: User, tmp_path) -> None:
        rows: list[ui.row] = []

        @ui.page('/')
        def page():
            rows.append(EditGridWrapper.from_list(Contact, [], title='Grid').render().title_row)
            rows.append(EditFormWrapper.from_json(Contact, tmp_path / 'c.json', title='Form').render().title_row)
            rows.append(DrillDownWrapper.from_list(Contact, [], list_title='List').render().title_row)

        await user.open('/')
        assert all(row is not None for row in rows)
        assert len({tuple(sorted(row.classes)) for row in rows}) == 1


# ---------------------------------------------------------------------------
# ModelList rows
# ---------------------------------------------------------------------------

def _icons(client) -> list[ui.icon]:
    return [e for e in client.layout.descendants() if isinstance(e, ui.icon)]


class TestModelListStyle:
    async def test_list_props_come_from_the_global_style(self, user: User) -> None:
        set_chrome_style(list_props='bordered')
        lists: list[ModelList] = []

        @ui.page('/')
        def page():
            lists.append(ModelList.from_list(Contact, [Contact(name='Alice')]).render())

        await user.open('/')
        assert lists[0].widget.props.get('bordered')
        assert not lists[0].widget.props.get('separator')

    async def test_item_classes_come_from_the_style(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [Contact(name='Alice')],
                                chrome_style=get_chrome_style().replace(list_item_classes='my-row')).render()

        await user.open('/')
        with user._client:
            items = [e for e in user.client.layout.descendants() if isinstance(e, ui.item)]
            assert items and 'my-row' in items[0].classes

    async def test_chevron_can_be_turned_off(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [Contact(name='Alice')],
                                chrome_style=ChromeStyle(list_chevron_icon=None)).render()

        await user.open('/')
        with user._client:
            assert _icons(user.client) == []

    async def test_chevron_icon_and_classes_are_configurable(self, user: User) -> None:
        set_chrome_style(list_chevron_icon='east', list_chevron_classes='text-primary')

        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [Contact(name='Alice')]).render()

        await user.open('/')
        with user._client:
            icons = _icons(user.client)
            assert icons and icons[0].props.get('name') == 'east'
            assert 'text-primary' in icons[0].classes

    async def test_subtitle_props_are_configurable(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [Contact(name='Alice', email='a@example.com')],
                                chrome_style=get_chrome_style().replace(list_subtitle_props='overline')).render()

        await user.open('/')
        with user._client:
            labels = [e for e in user.client.layout.descendants() if isinstance(e, ui.item_label)]
            subtitle = [e for e in labels if 'a@example.com' in e.text]
            assert subtitle and subtitle[0].props.get('overline')

    async def test_style_survives_update_rows(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        lists: list[ModelList] = []

        @ui.page('/')
        def page():
            lists.append(ModelList.from_list(Contact, contacts,
                                             chrome_style=ChromeStyle(list_item_classes='my-row')).render())

        await user.open('/')
        with user._client:
            lists[0].adapter.create(Contact(name='Bob'))
            lists[0].update_rows()
            items = [e for e in user.client.layout.descendants() if isinstance(e, ui.item)]
            assert len(items) == 2
            assert all('my-row' in i.classes for i in items)

    async def test_drilldown_passes_its_style_to_the_list(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [Contact(name='Alice')],
                                       chrome_style=ChromeStyle(list_chevron_icon=None)).render()

        await user.open('/')
        with user._client:
            assert _icons(user.client) == []


# ---------------------------------------------------------------------------
# DrillDownWrapper chrome options added along with the style
# ---------------------------------------------------------------------------

class TestDrillDownChromeOptions:
    async def test_back_button_can_be_labelled(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], on_back=lambda: None, back_button='Up').render()

        await user.open('/')
        await user.should_see('Up')

    async def test_back_button_none_hides_it(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], on_back=lambda: None,
                                       add_button=None, back_button=None).render()

        await user.open('/')
        await user.should_not_see(ui.button)

    async def test_back_button_none_survives_navigation(self, user: User) -> None:
        contacts = [Contact(name='Alice')]

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, contacts, back_button=None).render().open('0')

        await user.open('/')
        await user.should_see('Alice')  # the detail form rendered, no assertion tripped

    async def test_description_renders(self, user: User) -> None:
        wrapper: list[DrillDownWrapper] = []

        @ui.page('/')
        def page():
            wrapper.append(DrillDownWrapper.from_list(Contact, [], list_title='Contacts',
                                                      description='Pick a *contact*.').render())

        await user.open('/')
        assert isinstance(wrapper[0].description, ui.markdown)
        assert wrapper[0].description.content == 'Pick a *contact*.'

    async def test_list_title_none_shows_no_title(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], list_title=None).render()

        await user.open('/')
        with user._client:
            titles = [e.text for e in user.client.layout.descendants() if isinstance(e, ui.label)]
        assert 'Contact List' not in titles
