"""
Acceptance tests for ModelList and DrillDownWrapper.

DrillDownWrapper is embeddable (render() draws into the current NiceGUI
context, no page/route of its own), so its tests wrap render() in a plain
@ui.page like any other niceview widget.
"""
import pydantic
import pytest
from nicegui import ui
from nicegui.testing import User

from niceview.dataadapter import ListAdapter, DirectoryAdapter, FileEntry
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
# DrillDownWrapper — list view
# ---------------------------------------------------------------------------

class TestDrillDownWrapperListView:
    async def test_title_visible(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [Contact(name='Alice')], title='My Contacts').render()

        await user.open('/')
        await user.should_see('My Contacts')

    async def test_item_names_visible(self, user: User) -> None:
        contacts = [Contact(name='Alice Müller'), Contact(name='Bob Schmidt')]

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, contacts, title='Contacts').render()

        await user.open('/')
        await user.should_see('Alice Müller')
        await user.should_see('Bob Schmidt')

    async def test_subtitle_visible(self, user: User) -> None:
        contacts = [Contact(name='Alice', email='alice@example.com')]

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, contacts).render()

        await user.open('/')
        await user.should_see('alice@example.com')

    async def test_add_button_visible_by_default(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts').render()

        await user.open('/')
        await user.should_see(ui.button)

    async def test_add_button_hidden_when_none(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], title='Contacts', add_button=None).render()

        await user.open('/')
        await user.should_not_see(ui.button)

    async def test_render_list_item_overrides_default_rows(self, user: User) -> None:
        contacts = [Contact(name='Alice')]

        def custom_row(key, item, select):
            ui.label(f'Custom: {item.name}')

        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, contacts, render_list_item=custom_row).render()

        await user.open('/')
        await user.should_see('Custom: Alice')

    async def test_on_back_shows_back_button_in_list_view(self, user: User) -> None:
        @ui.page('/')
        def page():
            DrillDownWrapper.from_list(Contact, [], on_back=lambda: None).render()

        await user.open('/')
        await user.should_see(ui.button)


# ---------------------------------------------------------------------------
# DrillDownWrapper — navigating to the detail view
# ---------------------------------------------------------------------------

class TestDrillDownWrapperDetailView:
    async def test_open_shows_form_fields(self, user: User) -> None:
        contacts = [Contact(name='Alice', email='alice@example.com')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter).render().open(key)

        await user.open('/')
        await user.should_see('Name')
        await user.should_see('Email')

    async def test_open_shows_item_title(self, user: User) -> None:
        contacts = [Contact(name='Alice Müller', email='alice@example.com')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter, title_field='name').render().open(key)

        await user.open('/')
        await user.should_see('Alice Müller')

    async def test_delete_button_visible_by_default(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter).render().open(key)

        await user.open('/')
        await user.should_see(ui.button)

    async def test_delete_button_hidden_when_none(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter, delete_button=None).render().open(key)

        await user.open('/')
        await user.should_see('Name')  # detail view rendered
        with pytest.raises(AssertionError):
            user.find(content='delete')

    async def test_invalid_key_shows_not_found(self, user: User) -> None:
        adapter = ListAdapter(Contact, [])

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter).render().open('nonexistent-key')

        await user.open('/')
        await user.should_see("not found")

    async def test_back_returns_to_list_view(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])
        holder = {}

        @ui.page('/')
        def page():
            holder['wrapper'] = DrillDownWrapper.from_adapter(Contact, adapter).render().open(key)

        await user.open('/')
        await user.should_see('Name')
        holder['wrapper']._back()
        await user.should_not_see('Name')

    async def test_render_detail_overrides_default_form(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])

        def custom_detail(adapter, key, set_key):
            ui.label('Custom detail body')

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter, render_detail=custom_detail).render().open(key)

        await user.open('/')
        await user.should_see('Custom detail body')
        await user.should_not_see('Name')

    async def test_render_detail_set_key_updates_state_after_rename(self, user: User, tmp_path) -> None:
        # Realistic use case: a DirectoryAdapter's rename() fires from a "Name"
        # widget inside render_detail, well after the initial render.
        adapter = DirectoryAdapter(tmp_path)
        key = adapter.create().name
        holder = {}

        def custom_detail(adapter, key, set_key):
            ui.label(f'Editing {key}')

            def do_rename():
                set_key(adapter.rename(key, 'renamed-key'))
            ui.button('Rename', on_click=lambda: do_rename())

        @ui.page('/')
        def page():
            holder['wrapper'] = DrillDownWrapper.from_adapter(FileEntry, adapter, render_detail=custom_detail).render()
            holder['wrapper'].open(key)

        await user.open('/')
        await user.should_see(f'Editing {key}')
        user.find('Rename').click()
        await user.should_see('Editing renamed-key')
        assert holder['wrapper']._state['key'] == 'renamed-key'


# ---------------------------------------------------------------------------
# DrillDownWrapper — add / delete actions
# ---------------------------------------------------------------------------

class TestDrillDownWrapperActions:
    async def test_add_button_creates_item_and_opens_detail(self, user: User) -> None:
        adapter = ListAdapter(Contact, [])

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter).render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see('Name')
        assert len(list(adapter)) == 1

    async def test_on_add_overrides_default_create(self, user: User) -> None:
        adapter = ListAdapter(Contact, [])
        called: list[bool] = []

        def custom_add():
            called.append(True)

        @ui.page('/')
        def page():
            DrillDownWrapper.from_adapter(Contact, adapter, on_add=custom_add).render()

        await user.open('/')
        user.find(content='add').click()
        await user.should_see('Contact List')  # title still visible, still in list view
        assert called == [True]
        assert len(list(adapter)) == 0

    async def test_open_public_method_navigates(self, user: User) -> None:
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])

        @ui.page('/')
        def page():
            wrapper = DrillDownWrapper.from_adapter(Contact, adapter)
            wrapper.render()
            wrapper.open(key)

        await user.open('/')
        await user.should_see('Name')

    async def test_repeated_list_renders_do_not_leak_change_handlers(self, user: User) -> None:
        # _render_list_view() (the default, ModelList-backed branch) runs again on every
        # navigation back to the list -- each run used to create a fresh ModelList that
        # registered its own on_change handler on the adapter, since ModelList.render()
        # auto-registers reactive updates. That accumulated a growing chain of handlers
        # pointing at stale, already-deleted list widgets. DrillDownWrapper's own single
        # on_change registration (which re-renders the whole body) already covers this,
        # so ModelList's per-instance registration must be suppressed internally.
        contacts = [Contact(name='Alice')]
        adapter = ListAdapter(Contact, contacts)
        key = adapter.key_from_item(contacts[0])
        holder = {}

        @ui.page('/')
        def page():
            holder['wrapper'] = DrillDownWrapper.from_adapter(Contact, adapter)
            holder['wrapper'].render()

        await user.open('/')
        wrapper = holder['wrapper']
        for _ in range(5):
            wrapper.open(key)
            wrapper._back()
        assert len(adapter._change_handlers) == 1
