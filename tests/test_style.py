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
from niceview.modelform import ModelForm
from niceview.style import (ChromeStyle, FieldStyle, get_chrome_style, get_field_style,
                            set_chrome_style, set_field_style)
from niceview.text import ChromeText, get_chrome_text, set_chrome_text, text_of


class Contact(pydantic.BaseModel):
    name: str = pydantic.Field(default='', title='Name')
    email: str = pydantic.Field(default='', title='Email')


@pytest.fixture(autouse=True)
def restore_chrome_style():
    """Style, field style and texts are application-wide state — put them back after each test."""
    original, original_fields, original_text = get_chrome_style(), get_field_style(), get_chrome_text()
    yield
    set_chrome_style(original)
    set_field_style(original_fields)
    set_chrome_text(original_text)


def _buttons(client) -> list[ui.button]:
    return [e for e in client.layout.descendants() if isinstance(e, ui.button)]


def _tooltips(client) -> list[ui.tooltip]:
    return [e for e in client.layout.descendants() if isinstance(e, ui.tooltip)]


# ---------------------------------------------------------------------------
# ChromeStyle
# ---------------------------------------------------------------------------

class TestChromeStyle:
    def test_button_props_ship_empty(self):
        # The chrome decides where a button goes and what it means; how it looks is the
        # application's call. Only the role layer carries a default.
        assert ChromeStyle().toolbar_button_props == ''
        assert ChromeStyle().form_button_props == ''
        assert ChromeStyle().dialog_button_props == ''
        assert ChromeStyle().icon_button_props == ''
        assert ChromeStyle().labelled_button_props == ''
        assert ChromeStyle().delete_button_props == 'color=negative'

    def test_there_is_no_base_layer(self):
        # "every button of this application looks like that" is a type statement, and NiceGUI
        # already owns it: ui.button.default_props().
        assert not hasattr(ChromeStyle(), 'button_props')

    def test_delete_is_the_only_role_with_a_default(self):
        roles = ('add', 'edit', 'save', 'refresh', 'back', 'ok', 'cancel')
        assert all(getattr(ChromeStyle(), f'{role}_button_props') == '' for role in roles)

    def test_shape_overrides_start_at_none(self):
        # None inherits the global shape, '' suppresses it, a value replaces it.
        assert ChromeStyle().toolbar_icon_button_props is None
        assert ChromeStyle().form_icon_button_props is None
        assert ChromeStyle().dialog_icon_button_props is None

    def test_derived_starts_from_the_application_default(self):
        set_chrome_style(toolbar_button_props='flat', tooltips=False)
        derived = ChromeStyle.derived(toolbar_button_props='dense')
        assert derived.toolbar_button_props == 'dense'
        assert derived.tooltips is False  # everything else comes from the global default
        assert get_chrome_style().toolbar_button_props == 'flat'  # the global is untouched

    def test_replace_returns_a_copy(self):
        style = ChromeStyle(toolbar_button_props='flat')
        derived = style.replace(toolbar_button_props='dense')
        assert derived.toolbar_button_props == 'dense'
        assert style.toolbar_button_props == 'flat'  # the original is untouched

    def test_replace_keeps_the_other_attributes(self):
        derived = ChromeStyle(title_classes='text-h5 grow').replace(tooltips=False)
        assert derived.title_classes == 'text-h5 grow'
        assert derived.tooltips is False

    def test_replace_rejects_unknown_attributes(self):
        with pytest.raises(TypeError):
            ChromeStyle().replace(no_such_attribute='x')

    def test_set_chrome_style_with_keywords_changes_only_those(self):
        set_chrome_style(toolbar_button_props='dense')
        assert get_chrome_style().toolbar_button_props == 'dense'
        assert get_chrome_style().title_classes == ChromeStyle().title_classes

    def test_set_chrome_style_with_an_instance_replaces_wholesale(self):
        set_chrome_style(ChromeStyle(toolbar_button_props='outline'))
        assert get_chrome_style().toolbar_button_props == 'outline'

    def test_set_chrome_style_returns_the_new_style(self):
        assert set_chrome_style(tooltips=False) is get_chrome_style()


# ---------------------------------------------------------------------------
# The application-wide default reaches every wrapper
# ---------------------------------------------------------------------------

class TestGlobalChromeStyle:
    async def test_grid_wrapper_buttons_use_the_global_props(self, user: User) -> None:
        set_chrome_style(toolbar_button_props='outline')

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, []).render()

        await user.open('/')
        with user._client:
            assert all(b.props.get('outline') for b in _buttons(user.client))

    async def test_form_wrapper_buttons_use_the_global_props(self, user: User, tmp_path) -> None:
        set_chrome_style(toolbar_button_props='outline')

        @ui.page('/')
        def page():
            EditFormWrapper.from_json(Contact, tmp_path / 'contact.json').render()

        await user.open('/')
        with user._client:
            assert all(b.props.get('outline') for b in _buttons(user.client))

    async def test_drilldown_buttons_use_the_global_props(self, user: User) -> None:
        set_chrome_style(toolbar_button_props='outline')

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
        set_chrome_style(toolbar_button_props='outline')

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], chrome_style=ChromeStyle(toolbar_button_props='push')).render()

        await user.open('/')
        with user._client:
            buttons = _buttons(user.client)
            assert buttons and all(b.props.get('push') and not b.props.get('outline') for b in buttons)

    async def test_title_classes_reach_the_title_label(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='People',
                                      chrome_style=ChromeStyle.derived(title_classes='text-h4')).render()

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
            DrillDownWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert 'Add a new item' in [t.text for t in _tooltips(user.client)]

    async def test_the_two_add_buttons_agree_apart_from_their_shape(self, user: User) -> None:
        set_chrome_style(icon_button_props='round')
        buttons: dict[str, ui.button] = {}

        @ui.page('/')
        def page():
            buttons['grid'] = EditGridWrapper.from_list(Contact, [], title='Grid').render().add_button
            buttons['drilldown'] = DrillDownWrapper.from_list(Contact, [], title='List').render().add_button

        await user.open('/')
        grid_props = dict(buttons['grid'].props)
        drilldown_props = dict(buttons['drilldown'].props)
        # The grid's Add is joined into a group and stays square; the drill-down's stands alone
        # and is round. Everything that is not the shape has to match.
        assert drilldown_props.pop('round', None) is True
        assert 'round' not in grid_props
        assert grid_props == drilldown_props

    async def test_all_three_title_rows_share_their_classes(self, user: User, tmp_path) -> None:
        rows: list[ui.row] = []

        @ui.page('/')
        def page():
            rows.append(EditGridWrapper.from_list(Contact, [], title='Grid').render().title_row)
            rows.append(EditFormWrapper.from_json(Contact, tmp_path / 'c.json', title='Form').render().title_row)
            rows.append(DrillDownWrapper.from_list(Contact, [], title='List').render().title_row)

        await user.open('/')
        assert all(row is not None for row in rows)
        assert len({tuple(sorted(row.classes)) for row in rows}) == 1


# ---------------------------------------------------------------------------
# A button group needs something to join
# ---------------------------------------------------------------------------

def _groups(client) -> list[ui.button_group]:
    return [e for e in client.layout.descendants() if isinstance(e, ui.button_group)]


class TestButtonGrouping:
    async def test_several_grid_buttons_are_grouped(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert len(_groups(user.client)) == 1
            assert len(_buttons(user.client)) == 4

    async def test_a_lone_grid_button_is_not_grouped(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts',
                                      add_button=None, edit_button=None, delete_button=None).render()

        await user.open('/')
        with user._client:
            assert _groups(user.client) == []
            assert len(_buttons(user.client)) == 1

    async def test_a_lone_form_button_is_not_grouped(self, user: User, tmp_path) -> None:
        # autosave suppresses Save, leaving Refresh on its own.
        @ui.page('/')
        def page():
            EditFormWrapper.from_json(Contact, tmp_path / 'c.json', title='Contact', autosave=True).render()

        await user.open('/')
        with user._client:
            assert _groups(user.client) == []
            assert len(_buttons(user.client)) == 1

    async def test_both_form_buttons_are_grouped(self, user: User, tmp_path) -> None:
        @ui.page('/')
        def page():
            EditFormWrapper.from_json(Contact, tmp_path / 'c.json', title='Contact').render()

        await user.open('/')
        with user._client:
            assert len(_groups(user.client)) == 1

    async def test_drilldown_never_groups_add_and_delete(self, user: User) -> None:
        # Both are configured by default, but Add belongs to the list view and Delete to the
        # detail view — only one of them is ever on screen.
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert _groups(user.client) == []

    async def test_button_group_can_be_turned_off(self, user: User) -> None:
        set_chrome_style(button_group=False)

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert _groups(user.client) == []
            assert len(_buttons(user.client)) == 4

    async def test_ungrouped_buttons_share_a_container(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts',
                                      chrome_style=get_chrome_style().replace(
                                          button_group=False, button_row_classes='my-buttons')).render()

        await user.open('/')
        with user._client:
            containers = [e for e in user.client.layout.descendants() if 'my-buttons' in e.classes]
            assert len(containers) == 1
            assert len([e for e in containers[0].descendants() if isinstance(e, ui.button)]) == 4


# ---------------------------------------------------------------------------
# Shape: a button without a label is round
# ---------------------------------------------------------------------------

class TestButtonShape:
    async def test_nothing_is_shaped_by_default(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert not any(b.props.get('round') for b in _buttons(user.client))

    async def test_icon_only_button_takes_the_icon_shape(self, user: User) -> None:
        set_chrome_style(icon_button_props='round')

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert all(b.props.get('round') for b in _buttons(user.client))

    async def test_labelled_button_is_not_round(self, user: User) -> None:
        set_chrome_style(icon_button_props='round')

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts',
                                       add_button='Add', delete_button='Delete').render()

        await user.open('/')
        with user._client:
            labelled = [b for b in _buttons(user.client) if b.props.get('label')]
            assert labelled and not any(b.props.get('round') for b in labelled)

    async def test_shape_is_configurable(self, user: User) -> None:
        set_chrome_style(icon_button_props='rounded outline', labelled_button_props='glossy')

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts',
                                       add_button='Add', delete_button=None).render()

        await user.open('/')
        with user._client:
            back = [b for b in _buttons(user.client) if b.props.get('icon') == 'arrow_back'][0]
            add = [b for b in _buttons(user.client) if b.props.get('icon') == 'add'][0]
            assert back.props.get('rounded') and back.props.get('outline')
            assert add.props.get('glossy') and not add.props.get('rounded')

    async def test_role_props_win_over_the_shape(self, user: User) -> None:
        set_chrome_style(icon_button_props='round color=grey', delete_button_props='color=negative')

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            delete = [b for b in _buttons(user.client) if b.props.get('icon') == 'delete'][0]
            assert delete.props.get('color') == 'negative'
            assert delete.props.get('round')

    async def test_grouped_icon_buttons_stay_square(self, user: User) -> None:
        # A group joins straight edges — Quasar cannot join circles.
        set_chrome_style(icon_button_props='round')

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert not any(b.props.get('round') for b in _buttons(user.client))

    async def test_ungrouped_icon_buttons_are_round(self, user: User) -> None:
        set_chrome_style(icon_button_props='round', button_group=False)

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            buttons = _buttons(user.client)
            assert len(buttons) == 4
            assert all(b.props.get('round') for b in buttons)

    async def test_shape_in_group_lets_the_shape_through(self, user: User) -> None:
        set_chrome_style(icon_button_props='rounded', shape_in_group=True)

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            assert all(b.props.get('rounded') for b in _buttons(user.client))

    async def test_the_group_does_not_leak_into_later_buttons(self, user: User, tmp_path) -> None:
        # The context var has to be reset when the group closes: the form below renders a
        # single, ungrouped Refresh button, which must be round again.
        set_chrome_style(icon_button_props='round')
        forms: list[EditFormWrapper] = []

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Grid').render()
            forms.append(EditFormWrapper.from_json(Contact, tmp_path / 'c.json',
                                                   title='Form', autosave=True).render())

        await user.open('/')
        assert forms[0].refresh_button.props.get('round')


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
            wrapper.append(DrillDownWrapper.from_list(Contact, [], title='Contacts',
                                                      description='Pick a *contact*.').render())

        await user.open('/')
        assert isinstance(wrapper[0].description, ui.markdown)
        assert wrapper[0].description.content == 'Pick a *contact*.'

    async def test_title_empty_shows_no_title(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='').render()

        await user.open('/')
        with user._client:
            titles = [e.text for e in user.client.layout.descendants() if isinstance(e, ui.label)]
        assert 'Contact List' not in titles

    async def test_title_none_shows_auto_title(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title=None).render()

        await user.open('/')
        with user._client:
            titles = [e.text for e in user.client.layout.descendants() if isinstance(e, ui.label)]
        assert 'Contact List' in titles


# ---------------------------------------------------------------------------
# The place axis
# ---------------------------------------------------------------------------

class TestPlaces:
    async def test_a_wrapper_uses_the_toolbar_place(self, user: User) -> None:
        set_chrome_style(toolbar_button_props='outline', form_button_props='push')

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        with user._client:
            buttons = _buttons(user.client)
            assert buttons and all(b.props.get('outline') and not b.props.get('push') for b in buttons)

    async def test_an_embedded_wrapper_uses_the_form_place(self, user: User) -> None:
        # A form's editgrid renders an EditGridWrapper inside the form -- the one place where
        # niceview nests a wrapper (modelform._render_editgrid_widget).
        set_chrome_style(toolbar_button_props='outline', form_button_props='push')

        class Line(pydantic.BaseModel):
            text: str = ''

        class Order(pydantic.BaseModel):
            lines: list[Line] = []

        @ui.page('/')
        def page():
            ModelForm.from_item(Order()).render()

        await user.open('/')
        with user._client:
            buttons = _buttons(user.client)
            assert buttons and all(b.props.get('push') and not b.props.get('outline') for b in buttons)

    async def test_the_place_is_a_wrapper_option(self, user: User) -> None:
        set_chrome_style(form_button_props='push')
        wrappers: list[EditGridWrapper] = []

        @ui.page('/')
        def page():
            wrappers.append(EditGridWrapper.from_list(Contact, [], title='C', place='form').render())

        await user.open('/')
        assert wrappers[0].add_button.props.get('push')


# ---------------------------------------------------------------------------
# Shape per place
# ---------------------------------------------------------------------------

class TestShapePerPlace:
    async def test_a_place_can_replace_the_icon_shape(self, user: User) -> None:
        set_chrome_style(icon_button_props='round', form_icon_button_props='rounded',
                         button_group=False)
        wrappers: list[EditGridWrapper] = []

        @ui.page('/')
        def page():
            wrappers.append(EditGridWrapper.from_list(Contact, [], title='C', place='form').render())

        await user.open('/')
        add = wrappers[0].add_button
        assert add.props.get('rounded') and not add.props.get('round')

    async def test_an_empty_override_suppresses_the_shape(self, user: User) -> None:
        set_chrome_style(icon_button_props='round', toolbar_icon_button_props='',
                         button_group=False)
        wrappers: list[EditGridWrapper] = []

        @ui.page('/')
        def page():
            wrappers.append(EditGridWrapper.from_list(Contact, [], title='C').render())

        await user.open('/')
        assert not wrappers[0].add_button.props.get('round')

    async def test_none_inherits_the_global_shape(self, user: User) -> None:
        set_chrome_style(icon_button_props='round', button_group=False)
        wrappers: list[EditGridWrapper] = []

        @ui.page('/')
        def page():
            wrappers.append(EditGridWrapper.from_list(Contact, [], title='C').render())

        await user.open('/')
        assert wrappers[0].add_button.props.get('round')


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

def _dialogs(client) -> list[ui.dialog]:
    return [e for e in client.layout.descendants() if isinstance(e, ui.dialog)]


class TestDialogChrome:
    """The dialog functions are opened from a button: NiceGUI's User fixture needs the page
    handler to return before page setup completes, so a dialog cannot be awaited in it."""

    @staticmethod
    def _page(**kwargs):
        from niceview.util import confirm_dialog

        @ui.page('/')
        def page():
            async def show():
                await confirm_dialog('Sure?', 'Really?', **kwargs)
            ui.button('Open', on_click=show)

    async def test_dialog_shell_comes_from_the_style(self, user: User) -> None:
        set_chrome_style(dialog_style='width: 800px', dialog_title_classes='text-h4')
        self._page()

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Really?')
        with user._client:
            dialog = _dialogs(user.client)[0]
            assert dialog._style.get('width') == '800px'
            titles = [e for e in dialog.descendants() if isinstance(e, ui.label) and e.text == 'Sure?']
            assert titles and 'text-h4' in titles[0].classes

    async def test_dialog_buttons_use_the_dialog_place_and_the_roles(self, user: User) -> None:
        set_chrome_style(dialog_button_props='flat', cancel_button_props='color=grey',
                         toolbar_button_props='outline')
        self._page()

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Really?')
        with user._client:
            buttons = _buttons(user.client)[1:]  # [0] is the page's own Open button
            assert buttons and all(b.props.get('flat') and not b.props.get('outline') for b in buttons)
            cancel = [b for b in buttons if b.props.get('label') == 'Cancel'][0]
            assert cancel.props.get('color') == 'grey'

    async def test_ok_role_picks_the_role_layer(self, user: User) -> None:
        self._page(ok_label='Delete', ok_role='delete')

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Really?')
        with user._client:
            ok = [b for b in _buttons(user.client) if b.props.get('label') == 'Delete'][0]
            assert ok.props.get('color') == 'negative'

    async def test_the_confirm_button_has_no_color_of_its_own(self, user: User) -> None:
        # 'color=primary' used to be spelled out for the confirm button. It is gone: a
        # ui.button is primary anyway, so niceview was repeating NiceGUI's default -- and now
        # both dialog buttons look alike until the application says otherwise.
        self._page()

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Really?')
        with user._client:
            by_label = {b.props.get('label'): b for b in _buttons(user.client)}
            assert by_label['OK'].props.get('color') == by_label['Cancel'].props.get('color')


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class TestNotifications:
    def test_the_hook_replaces_ui_notify(self) -> None:
        from niceview.style import chrome_notify
        seen: list[tuple[str, str]] = []
        style = ChromeStyle(notify=lambda message, kind: seen.append((message, kind)))
        chrome_notify('saved', 'positive', style)
        assert seen == [('saved', 'positive')]

    def test_options_reach_ui_notify(self) -> None:
        from unittest.mock import patch
        from niceview.style import chrome_notify
        style = ChromeStyle(notify_position='top', notify_timeout=1.5, notify_close_button=True)
        with patch.object(ui, 'notify') as notify:
            chrome_notify('saved', 'positive', style)
        notify.assert_called_once_with('saved', type='positive', position='top',
                                       timeout=1.5, close_button=True)


# ---------------------------------------------------------------------------
# Title levels
# ---------------------------------------------------------------------------

class TestTitleLevels:
    async def test_card_and_section_titles_have_their_own_classes(self, user: User) -> None:
        set_chrome_style(card_title_classes='card-title', section_title_classes='section-title')

        class Person(pydantic.BaseModel):
            first: str = ''
            last: str = ''

        @ui.page('/')
        def page():
            ModelForm.from_item(Person(), layout=[['# Card', 'first'], ['## Section', 'last']]).render()

        await user.open('/')
        with user._client:
            labels = {e.text: e.classes for e in user.client.layout.descendants()
                      if isinstance(e, ui.label)}
            assert 'card-title' in labels['Card']
            assert 'section-title' in labels['Section']


# ---------------------------------------------------------------------------
# FieldStyle
# ---------------------------------------------------------------------------

class TestFieldStyle:
    def test_ships_empty(self) -> None:
        assert FieldStyle() == FieldStyle(input_props='', control_props='', default_classes='')

    async def test_input_props_reach_the_input_based_widgets_only(self, user: User) -> None:
        set_field_style(input_props='outlined', control_props='dense')

        class Mixed(pydantic.BaseModel):
            name: str = ''
            active: bool = False

        forms: list[ModelForm] = []

        @ui.page('/')
        def page():
            forms.append(ModelForm.from_item(Mixed()).render())

        await user.open('/')
        assert forms[0].w('name').props.get('outlined')
        assert not forms[0].w('active').props.get('outlined')
        assert forms[0].w('active').props.get('dense')

    async def test_the_form_layer_wins_over_the_application_layer(self, user: User) -> None:
        set_field_style(input_props='outlined color=grey')

        class Person(pydantic.BaseModel):
            name: str = ''

        forms: list[ModelForm] = []

        @ui.page('/')
        def page():
            forms.append(ModelForm.from_item(Person(), base_props='color=primary').render())

        await user.open('/')
        widget = forms[0].w('name')
        assert widget.props.get('outlined')          # additive per key
        assert widget.props.get('color') == 'primary'  # the narrower layer wins

    async def test_default_classes_are_a_fallback(self, user: User) -> None:
        set_field_style(default_classes='w-full')

        class Person(pydantic.BaseModel):
            name: str = ''
            nick: str = ''

        forms: list[ModelForm] = []

        @ui.page('/')
        def page():
            forms.append(ModelForm.from_item(Person(), field_infos={
                'nick': __import__('niceview').Field(classes='w-1/2')}).render())

        await user.open('/')
        assert 'w-full' in forms[0].w('name').classes
        assert 'w-full' not in forms[0].w('nick').classes

    async def test_field_style_reaches_the_model_free_render_field(self, user: User) -> None:
        # The application-wide FieldStyle applies to niceview.render_field() too, not just to a
        # ModelForm: the category props and the default_classes fallback, with a field's own
        # props/classes still winning.
        import niceview
        set_field_style(input_props='outlined', control_props='dense', default_classes='w-full')

        widgets: dict = {}

        @ui.page('/')
        def page():
            widgets['name'] = niceview.render_field(niceview.Field(widget_type='ui.input'))
            widgets['active'] = niceview.render_field(niceview.Field(widget_type='ui.switch'))
            widgets['own'] = niceview.render_field(niceview.Field(widget_type='ui.input', classes='w-1/2'))

        await user.open('/')
        assert widgets['name'].props.get('outlined')        # input_props on an input
        assert not widgets['active'].props.get('outlined')  # not on a control
        assert widgets['active'].props.get('dense')         # control_props on a switch
        assert 'w-full' in widgets['name'].classes          # default_classes fallback
        assert 'w-full' not in widgets['own'].classes       # a field's own classes win
        assert 'w-1/2' in widgets['own'].classes


# ---------------------------------------------------------------------------
# ChromeText
# ---------------------------------------------------------------------------

class TestChromeText:
    def test_text_of_resolves_a_callable(self) -> None:
        assert text_of('plain') == 'plain'
        assert text_of(lambda: 'called') == 'called'

    def test_text_of_fills_named_placeholders(self) -> None:
        assert text_of('Error: {error}', error='boom') == 'Error: boom'

    def test_text_of_leaves_a_template_alone_without_params(self) -> None:
        # A text may contain braces of its own; formatting it would raise.
        assert text_of('{not a placeholder}') == '{not a placeholder}'

    def test_derived_starts_from_the_application_default(self) -> None:
        set_chrome_text(ok_label='Ok')
        derived = ChromeText.derived(cancel_label='Abbrechen')
        assert derived.ok_label == 'Ok'
        assert derived.cancel_label == 'Abbrechen'

    async def test_tooltips_come_from_the_texts(self, user: User) -> None:
        set_chrome_text(add_tooltip='Neuen Eintrag anlegen')

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Kontakte').render()

        await user.open('/')
        with user._client:
            assert 'Neuen Eintrag anlegen' in [t.text for t in _tooltips(user.client)]

    async def test_a_callable_is_resolved_at_render_time(self, user: User) -> None:
        language = {'current': 'en'}
        set_chrome_text(add_tooltip=lambda: 'Hinzufügen' if language['current'] == 'de' else 'Add')
        language['current'] = 'de'

        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='Kontakte').render()

        await user.open('/')
        with user._client:
            assert 'Hinzufügen' in [t.text for t in _tooltips(user.client)]

    async def test_dialog_labels_come_from_the_texts(self, user: User) -> None:
        from niceview.util import confirm_dialog
        set_chrome_text(ok_label='Ja', cancel_label='Nein')

        @ui.page('/')
        def page():
            async def show():
                await confirm_dialog('Sicher?', 'Wirklich?')
            ui.button('Open', on_click=show)

        await user.open('/')
        user.find('Open').click()
        await user.should_see('Ja')
        await user.should_see('Nein')

    async def test_the_required_marker_comes_from_the_texts(self, user: User) -> None:
        set_chrome_text(required_marker=' !')

        class Person(pydantic.BaseModel):
            name: str

        forms: list[ModelForm] = []

        @ui.page('/')
        def page():
            forms.append(ModelForm.from_item(Person(name='x')).render())

        await user.open('/')
        assert forms[0].w('name').props.get('label').endswith(' !')

    async def test_a_widget_can_override_the_texts(self, user: User) -> None:
        @ui.page('/')
        def page():
            EditGridWrapper.from_list(Contact, [], title='C',
                                      chrome_text=ChromeText.derived(add_tooltip='Nur hier')).render()

        await user.open('/')
        with user._client:
            assert 'Nur hier' in [t.text for t in _tooltips(user.client)]
