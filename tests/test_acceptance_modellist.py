"""
Acceptance tests for ModelList and DrillDownWrapper.

The NiceGUI testing framework resets routes between tests, so DrillDownWrapper
pages cannot be registered at module level. Instead, DrillDownWrapper rendering
is tested by calling _render_list_page / _render_detail_page directly inside
@ui.page('/') — this exercises the rendering logic without coupling to URL routing,
which is NiceGUI/FastAPI's responsibility.
"""
import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User

from niceview.dataadapter import ListAdapter
from niceview.modellist import ModelList, DrillDownWrapper


class Contact(pydantic.BaseModel):
    name: str = pydantic.Field(default='', title='Name')
    email: str = pydantic.Field(default='', title='Email')
    phone: str = pydantic.Field(default='', title='Phone')


# ---------------------------------------------------------------------------
# ModelList — render
# ---------------------------------------------------------------------------

class TestModelListRender:
    async def test_item_titles_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [
                Contact(name='Alice', email='alice@example.com'),
                Contact(name='Bob', email='bob@example.com'),
            ]).render()

        await user.open('/')
        await user.should_see('Alice')
        await user.should_see('Bob')

    async def test_subtitle_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [
                Contact(name='Alice', email='alice@example.com'),
            ]).render()

        await user.open('/')
        await user.should_see('alice@example.com')

    async def test_empty_list_renders_without_error(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, []).render()

        await user.open('/')
        await user.should_not_see('Alice')

    async def test_explicit_title_field(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [
                Contact(name='Alice', email='alice@example.com'),
            ], title_field='email').render()

        await user.open('/')
        await user.should_see('alice@example.com')

    async def test_custom_subtitle_fields(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [
                Contact(name='Alice', email='alice@example.com', phone='123'),
            ], subtitle_fields=['phone']).render()

        await user.open('/')
        await user.should_see('123')

    async def test_widget_element_present(self, user: User) -> None:
        @ui.page('/')
        def page():
            ModelList.from_list(Contact, [Contact(name='Alice')]).render()

        await user.open('/')
        await user.should_see(ui.list)

    async def test_on_select_non_callable_raises(self) -> None:
        ml = ModelList.from_list(Contact, [])
        with pytest.raises(TypeError):
            ml.on_select('not callable')  # type: ignore


# ---------------------------------------------------------------------------
# DrillDownWrapper — list page rendering
# ---------------------------------------------------------------------------

class TestDrillDownWrapperListPage:
    async def test_title_in_header(self, user: User) -> None:
        wrapper = DrillDownWrapper.from_list(Contact, [Contact(name='Alice')], title='My Contacts')

        @ui.page('/')
        def page():
            wrapper._render_list_page('/contacts')

        await user.open('/')
        await user.should_see('My Contacts')

    async def test_item_names_visible(self, user: User) -> None:
        contacts = [Contact(name='Alice Müller'), Contact(name='Bob Schmidt')]
        wrapper = DrillDownWrapper.from_list(Contact, contacts, title='Contacts')

        @ui.page('/')
        def page():
            wrapper._render_list_page('/contacts')

        await user.open('/')
        await user.should_see('Alice Müller')
        await user.should_see('Bob Schmidt')

    async def test_subtitle_visible(self, user: User) -> None:
        contacts = [Contact(name='Alice', email='alice@example.com')]
        wrapper = DrillDownWrapper.from_list(Contact, contacts)

        @ui.page('/')
        def page():
            wrapper._render_list_page('/contacts')

        await user.open('/')
        await user.should_see('alice@example.com')

    async def test_add_button_visible_by_default(self, user: User) -> None:
        wrapper = DrillDownWrapper.from_list(Contact, [], title='Contacts')

        @ui.page('/')
        def page():
            wrapper._render_list_page('/contacts')

        await user.open('/')
        await user.should_see(ui.button)

    async def test_add_button_hidden_when_none(self, user: User) -> None:
        wrapper = DrillDownWrapper.from_list(Contact, [], title='Contacts', add_button=None)

        @ui.page('/')
        def page():
            wrapper._render_list_page('/contacts')

        await user.open('/')
        await user.should_not_see(ui.button)


# ---------------------------------------------------------------------------
# DrillDownWrapper — detail page rendering
# ---------------------------------------------------------------------------

class TestDrillDownWrapperDetailPage:
    async def test_form_fields_visible(self, user: User) -> None:
        contacts = [Contact(name='Alice', email='alice@example.com')]
        adapter = ListAdapter(Contact, contacts)
        wrapper = DrillDownWrapper.from_adapter(Contact, adapter)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            wrapper._render_detail_page('/contacts', key)

        await user.open('/')
        await user.should_see('Name')
        await user.should_see('Email')

    async def test_item_title_in_header(self, user: User) -> None:
        contacts = [Contact(name='Alice Müller', email='alice@example.com')]
        adapter = ListAdapter(Contact, contacts)
        wrapper = DrillDownWrapper.from_adapter(Contact, adapter, title_field='name')
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            wrapper._render_detail_page('/contacts', key)

        await user.open('/')
        await user.should_see('Alice Müller')

    async def test_back_button_present(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        wrapper = DrillDownWrapper.from_adapter(Contact, adapter)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            wrapper._render_detail_page('/contacts', key)

        await user.open('/')
        await user.should_see(ui.button)

    async def test_delete_button_visible_by_default(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        wrapper = DrillDownWrapper.from_adapter(Contact, adapter)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            wrapper._render_detail_page('/contacts', key)

        await user.open('/')
        await user.should_see(ui.button)

    async def test_invalid_key_shows_not_found(self, user: User) -> None:
        adapter = ListAdapter(Contact, [])
        wrapper = DrillDownWrapper.from_adapter(Contact, adapter)

        @ui.page('/')
        def page():
            wrapper._render_detail_page('/contacts', 'nonexistent-key')

        await user.open('/')
        await user.should_see('Not Found')


# ---------------------------------------------------------------------------
# DrillDownWrapper — split-panel layout
# ---------------------------------------------------------------------------

class TestDrillDownWrapperSplitPanel:
    async def test_list_page_renders_list_widget(self, user: User) -> None:
        contacts = [Contact(name='Alice'), Contact(name='Bob')]
        wrapper = DrillDownWrapper.from_list(Contact, contacts, title='Contacts')

        @ui.page('/')
        def page():
            wrapper._render_list_page('/contacts')

        await user.open('/')
        await user.should_see(ui.list)

    async def test_detail_page_renders_list_for_side_panel(self, user: User) -> None:
        contacts = [Contact(name='Alice'), Contact(name='Bob')]
        adapter = ListAdapter(Contact, contacts)
        wrapper = DrillDownWrapper.from_adapter(Contact, adapter)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            wrapper._render_detail_page('/contacts', key)

        await user.open('/')
        # The detail page renders a list for the desktop side panel
        await user.should_see(ui.list)

    async def test_detail_page_renders_form_and_list(self, user: User) -> None:
        contacts = [Contact(name='Alice', email='alice@example.com'), Contact(name='Bob')]
        adapter = ListAdapter(Contact, contacts)
        wrapper = DrillDownWrapper.from_adapter(Contact, adapter)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            wrapper._render_detail_page('/contacts', key)

        await user.open('/')
        # Form fields rendered
        await user.should_see('Name')
        # Side panel list also rendered (desktop split-panel)
        await user.should_see('Bob')
