import datetime
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo
import pydantic
import sqlmodel
from nicegui import ui

import niceview
from niceview.modeledit import EditGridWrapper
from niceview.modelform import ModelForm
from niceview.modelgrid import ModelGridInlineEdit, ModelGrid
from niceview.dataadapter import ListModelAdapter, JsonListModelAdapter


def now_factory():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


class Group(pydantic.BaseModel):
    name: str = pydantic.Field(max_length=50, title="Group Name", description="Name of the group", default='')

    def __str__(self):
        return self.name


class User(pydantic.BaseModel):
    name: str = pydantic.Field(max_length=8, title="Name", description="Full name of the user", default='')
    age: Annotated[int, pydantic.Field(default=30), niceview.Field(min=0, max=150, label="User's Age")]
    num: int = 0
    is_active: bool = True
    is_admin: Annotated[bool, pydantic.Field(default=True), niceview.Field(widget_type='ui.checkbox', classes='text-red-500')]
    birthdate: datetime.date = datetime.date.today()
    birthtime: datetime.time = pydantic.Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).time(), title="Time of birth", description="User's time of birth (UTC)")
    birthdatetime: Annotated[datetime.datetime, pydantic.Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0), title="Birthdate & Time", description="User's birthdate and time (UTC)")]
    until_birthday: datetime.timedelta = pydantic.Field(default_factory=lambda: datetime.timedelta(days=5), title="Until next birthday", description="Time until the next birthday")
    gender: Literal['male', 'female', 'other'] = 'other'
    vegetarian: Literal['Yes', 'No', None] = None
    favorite_dishes: list[str] = []
    groups: Annotated[list[Group], pydantic.Field(default_factory=list, title="Groups", description="List of groups the user belongs to"), niceview.Field()]


user = User(name='John Doe', age=30, num=42, is_active=True, is_admin=False, birthdatetime=datetime.datetime(1990, 1, 1, 12, 0), gender='male', vegetarian='Yes', favorite_dishes=['Sushi', 'Pizza'], groups=[Group(name='Admin'), Group(name='User')])
user_list = [
    user, 
    User(name='Jane Doe', age=25, num=43), 
    User(name='Alice', age=28, num=44), 
    User(name='Bob', age=35, num=45), 
    User(name='Charlie', age=40, num=46), 
    User(name='Dave', age=45, num=47), 
    User(name='Eve', age=50, num=48), 
    User(name='Frank', age=55, num=49), 
    User(name='Grace', age=60, num=50)
]

USER_PATH: Path = Path('./user.json')
GROUPS_PATH: Path = Path('./groups.json')

@ui.page('/form')
def form_page():

    def refresh_groups():
        groups_label.text = f'Groups: {", ".join(g.name for g in user.groups)}'

    with ui.row():
        user_form = ModelForm.from_item(user, classes='w-full')
        with ui.card():
            ui.label('Example for a User Form:')
            user_form.render()

        with ui.card():
            ui.label('Binding example - Values of the User Form fields:')
            ui.label().bind_text_from(user, 'name')
            ui.label().bind_text_from(user, 'age')
            ui.label().bind_text_from(user, 'num')
            ui.label('is active').bind_visibility_from(user, 'is_active')
            ui.label('is admin').bind_visibility_from(user, 'is_admin')
            ui.label().bind_text_from(user, 'birthdate')
            ui.label().bind_text_from(user, 'birthtime')
            ui.label().bind_text_from(user, 'birthdatetime')
            ui.label().bind_text_from(user, 'until_birthday', backward=lambda td: str(td))
            ui.label().bind_text_from(user, 'gender')
            ui.label().bind_text_from(user, 'vegetarian')
            ui.label().bind_text_from(user, 'favorite_dishes')

            groups_label = ui.label(f'Groups: {", ".join(g.name for g in user.groups)}')
            with ui.row():
                ui.button('num++', on_click=lambda: setattr(user, 'num', user.num + 1))
                ui.button('num--', on_click=lambda: setattr(user, 'num', user.num - 1))

    user_form.on_change(lambda e: refresh_groups() if e.field_name == 'groups' else None)
    user_form.on_change(lambda e: print(f'on_change: {e.form=} {e.field_name=} {e.old_value=} {e.new_value=} {e.sender=} {e.client=}'))


@ui.page('/form_json_autosave')
def form_json_page_autosave():
    with ui.card().classes('w-full'):
        ui.label('Example for a User Form (JSON file, autosave)').classes('text-h6')
        user_form_autosave = ModelForm.from_json(User, USER_PATH, autosave=True, classes='w-full')
        user_form_autosave.render()


@ui.page('/form_json_buttons')
def form_json_page_buttons():
    with ui.card().classes('w-full'):
        title = f'User Form with refresh and save buttons (JSON file {USER_PATH}, save button)'
        user_form_buttons = ModelForm.from_json(User, USER_PATH, title=title, save_button='', classes='w-full')
        user_form_buttons.render()


@ui.page('/grid')
def grid_page():
    with ui.card().classes('w-full'):
        ui.label('Simple readonly AgGrid').classes('text-h6')
        user_grid_simple = ModelGrid(User, ListModelAdapter(User, user_list), fields=['name', 'age', 'num'], classes='w-full')
        user_grid_simple.render()

    with ui.card().classes('w-full'):
        ui.label('Inline-editable AgGrid').classes('text-h6')
        user_grid_inlineedit = ModelGridInlineEdit(
            User, ListModelAdapter(User, user_list), 
            rowSelection='single', 
        )
        user_grid_inlineedit.render()
        user_grid_inlineedit.on_change(lambda e: print(f'inline on_change: {e.model_table=} {e.row_key=} {e.item=} {e.field_name} {e.new_value} {e.sender=} {e.client=}'))

    with ui.card().classes('w-full'):
        ui.label('AgGrid in a EditGridWrapper').classes('text-h6')
        user_grid_edit = EditGridWrapper(
            ModelGrid(
                User, 
                ListModelAdapter(User, user_list), 
                fields=['name', 'age', 'num', 'is_active', 'birthdatetime', 'gender'], 
            ),
            title='Example for an editable AgGrid', 
        )
        user_grid_edit.render()
        user_grid_edit.on_change(lambda e: print(f'edit on_change: {e.model_table=} {e.row_key=} {e.item=} {e.sender=} {e.client=}'))


@ui.page('/grid_json')
def grid_json_page():
    adapter = JsonListModelAdapter(Group, GROUPS_PATH)

    with ui.card().classes('w-full'):
        ui.label('Readonly AgGrid backed by JSON file').classes('text-h6')
        ModelGrid(Group, adapter, classes='w-full').render()

    with ui.card().classes('w-full'):
        ui.label('Inline-editable AgGrid (changes persist to JSON immediately)').classes('text-h6')
        ModelGridInlineEdit(Group, adapter, classes='w-full').render()

    with ui.card().classes('w-full'):
        EditGridWrapper(
            ModelGridInlineEdit(Group, adapter, classes='w-full'),
            title='Groups — full CRUD, persisted to JSON',
        ).render()


@ui.page('/')
def main_page():
    ui.label('Welcome to the NiceView Example!').classes('text-h3')
    ui.label('Non-SQLModel Version').classes('text-subtitle2')
    with ui.row():
        ui.button('Form Example', on_click=lambda: ui.navigate.to('/form')).classes('q-mr-sm')
        ui.button('Form Example (JSON autosave)', on_click=lambda: ui.navigate.to('/form_json_autosave')).classes('q-mr-sm')
        ui.button('Form Example (JSON Buttons)', on_click=lambda: ui.navigate.to('/form_json_buttons')).classes('q-mr-sm')
        ui.button('ModelGrid Example', on_click=lambda: ui.navigate.to('/grid')).classes('q-mr-sm')
        ui.button('ModelGrid JSON Example', on_click=lambda: ui.navigate.to('/grid_json')).classes('q-mr-sm')

ui.run()
