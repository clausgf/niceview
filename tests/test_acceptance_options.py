"""
Acceptance tests for the unified `options` FieldInfo attribute and for
sync/async callable option sources (select / radio / toggle / checkbox_group).
"""
import asyncio
from typing import Annotated, Literal

import pydantic
from nicegui import ui
from nicegui.testing import User

import niceview
from niceview import ModelForm
from niceview.form import CheckboxGroup


class TestUnifiedOptions:
    async def test_options_on_select(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.select', options=['red', 'green'])] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('color', ui.select).options == ['red', 'green']

    async def test_options_on_radio(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.radio', options=['red', 'green'])] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('color', ui.radio).options == ['red', 'green']

    async def test_options_on_toggle(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.toggle', options=['red', 'green'])] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('color', ui.toggle).options == ['red', 'green']

    async def test_options_on_checkbox_group(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            perms: Annotated[list[str], niceview.Field(widget_type='checkbox_group', options=['read', 'write'])] = \
                pydantic.Field(default_factory=list)

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('perms', CheckboxGroup).options == ['read', 'write']

    async def test_options_wins_over_specific_alias(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.select',
                                                 options=['red', 'green'],
                                                 select_options=['blue'])] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('color', ui.select).options == ['red', 'green']

    async def test_specific_alias_still_works(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.select', select_options=['red', 'green'])] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('color', ui.select).options == ['red', 'green']

    async def test_literal_fallback_unchanged(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            color: Literal['red', 'green'] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('color', ui.select).options == ['red', 'green']


class TestCallableOptions:
    async def test_sync_callable_options(self, user: User) -> None:
        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.select',
                                                 options=lambda: ['red', 'green'])] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        assert captured[0].w('color', ui.select).options == ['red', 'green']

    async def test_async_callable_options_select(self, user: User) -> None:
        async def load_options() -> list[str]:
            await asyncio.sleep(0.01)
            return ['red', 'green']

        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.select', options=load_options)] = 'red'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        widget = captured[0].w('color', ui.select)
        assert widget.options == []            # placeholder until the async source resolves
        await asyncio.sleep(0.05)
        assert widget.options == ['red', 'green']
        assert widget.value == 'red'           # item value re-applied after late options

    async def test_async_callable_options_radio(self, user: User) -> None:
        async def load_options() -> list[str]:
            await asyncio.sleep(0.01)
            return ['red', 'green']

        class Item(pydantic.BaseModel):
            color: Annotated[str, niceview.Field(widget_type='ui.radio', options=load_options)] = 'green'

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        widget = captured[0].w('color', ui.radio)
        await asyncio.sleep(0.05)
        assert widget.options == ['red', 'green']
        assert widget.value == 'green'

    async def test_async_callable_options_checkbox_group(self, user: User) -> None:
        async def load_options() -> list[str]:
            await asyncio.sleep(0.01)
            return ['read', 'write']

        class Item(pydantic.BaseModel):
            perms: Annotated[list[str], niceview.Field(widget_type='checkbox_group', options=load_options)] = \
                pydantic.Field(default_factory=lambda: ['write'])

        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(Item())
            form.render()
            captured.append(form)

        await user.open('/')
        group = captured[0].w('perms', CheckboxGroup)
        await asyncio.sleep(0.05)
        assert group.options == ['read', 'write']
        assert group.value == ['write']        # item value re-applied after rebuild

    async def test_checkbox_group_change_after_async_options_updates_model(self, user: User) -> None:
        async def load_options() -> list[str]:
            await asyncio.sleep(0.01)
            return ['read', 'write']

        class Item(pydantic.BaseModel):
            perms: Annotated[list[str], niceview.Field(widget_type='checkbox_group', options=load_options)] = \
                pydantic.Field(default_factory=list)

        item = Item()
        captured: list[ModelForm] = []

        @ui.page('/')
        def page():
            form = ModelForm.from_item(item)
            form.render()
            captured.append(form)

        await user.open('/')
        await asyncio.sleep(0.05)
        group = captured[0].w('perms', CheckboxGroup)
        group.checkboxes['read'].value = True  # rebuilt checkboxes must still be wired to the form
        assert item.perms == ['read']
