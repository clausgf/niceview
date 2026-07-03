"""
Example 11 – Multi-level tree navigation with explicit back buttons.

Level 1  /projects                        Card grid of all projects
Level 2  /projects/{pid}                  Edit project + buttons to sub-collections
Level 3  /projects/{pid}/tasks            Task list (ModelList)
Level 4  /projects/{pid}/tasks/{tid}      Task detail form (EditFormWrapper)
Level 3  /projects/{pid}/notes            Notes list (ModelList)
Level 4  /projects/{pid}/notes/{nid}      Note detail form (EditFormWrapper)

URL patterns live in one place (class R).  Every sub-page shows an explicit
back button.  Replace the in-memory ListAdapters with JsonListAdapter or
SqlModelAdapter to add persistence without changing the page logic.
"""

from typing import Literal
from nicegui import ui
from pydantic import BaseModel, Field

from niceview.dataadapter import ListAdapter, FilteredAdapter
from niceview.modellist import ModelList
from niceview.wrapper import EditFormWrapper


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Project(BaseModel):
    name: str = Field(default='', title='Name', max_length=50)
    description: str = Field(default='', title='Description')
    status: Literal['planning', 'active', 'done'] = Field(default='planning', title='Status')
    budget: float = Field(default=0.0, title='Budget (k€)', ge=0)

    def __str__(self) -> str:
        return self.name


class Task(BaseModel):
    project_key: str = Field(default='')   # ListAdapter key of the parent project
    title: str = Field(default='', title='Title', max_length=100)
    priority: Literal['low', 'medium', 'high'] = Field(default='medium', title='Priority')
    done: bool = Field(default=False, title='Done')

    def __str__(self) -> str:
        return self.title


class Note(BaseModel):
    project_key: str = Field(default='')   # ListAdapter key of the parent project
    text: str = Field(default='', title='Note', max_length=500)
    author: str = Field(default='', title='Author', max_length=50)

    def __str__(self) -> str:
        return self.text[:50]


# ---------------------------------------------------------------------------
# In-memory storage
# ListAdapter assigns sequential keys: first project → "0", second → "1", …
# project_key in Task/Note matches those string keys.
# ---------------------------------------------------------------------------

projects_adapter = ListAdapter(Project, [
    Project(name='Website Relaunch', description='Redesign and relaunch our corporate website.',
            status='active', budget=45.0),
    Project(name='Mobile App', description='Native app for iOS and Android.',
            status='planning', budget=120.0),
    Project(name='API Migration', description='Migrate REST API to GraphQL.',
            status='done', budget=30.0),
])

tasks_adapter = ListAdapter(Task, [
    Task(project_key='0', title='Create wireframes',      priority='high',   done=True),
    Task(project_key='0', title='Implement homepage',     priority='high',   done=False),
    Task(project_key='0', title='Write tests',            priority='medium', done=False),
    Task(project_key='1', title='Define requirements',    priority='high',   done=True),
    Task(project_key='1', title='Setup CI/CD',            priority='medium', done=False),
])

notes_adapter = ListAdapter(Note, [
    Note(project_key='0', text='Consider accessibility from the start.', author='Alice'),
    Note(project_key='0', text='Budget includes two years of hosting.',  author='Bob'),
    Note(project_key='1', text='iOS release first, Android follows in Q2.', author='Alice'),
])


# ---------------------------------------------------------------------------
# Route definitions — single source of truth for all URLs
# ---------------------------------------------------------------------------

class R:
    """URL factory: PATTERN_* constants for @ui.page(), static methods for ui.navigate.to()."""

    PATTERN_PROJECTS = '/projects'
    PATTERN_PROJECT  = '/projects/{pid}'
    PATTERN_TASKS    = '/projects/{pid}/tasks'
    PATTERN_TASK     = '/projects/{pid}/tasks/{tid}'
    PATTERN_NOTES    = '/projects/{pid}/notes'
    PATTERN_NOTE     = '/projects/{pid}/notes/{nid}'

    @staticmethod
    def projects() -> str:
        return '/projects'

    @staticmethod
    def project(pid: str) -> str:
        return f'/projects/{pid}'

    @staticmethod
    def tasks(pid: str) -> str:
        return f'/projects/{pid}/tasks'

    @staticmethod
    def task(pid: str, tid: str) -> str:
        return f'/projects/{pid}/tasks/{tid}'

    @staticmethod
    def notes(pid: str) -> str:
        return f'/projects/{pid}/notes'

    @staticmethod
    def note(pid: str, nid: str) -> str:
        return f'/projects/{pid}/notes/{nid}'


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

_STATUS_COLOR = {'planning': 'blue', 'active': 'green', 'done': 'grey'}


def _fields_full_width(wrapper: EditFormWrapper) -> None:
    """Make all rendered form fields full width (layout-only, no NiceView API change)."""
    for widget in wrapper.form.widgets.values():
        if hasattr(widget, 'classes') and callable(widget.classes):
            widget.classes('w-full')


def page_header(title: str, back_url: str | None = None) -> None:
    """App bar with optional back button (always visible, never just the browser back)."""
    with ui.header().classes('items-center gap-1'):
        if back_url:
            ui.button(icon='arrow_back',
                      on_click=lambda: ui.navigate.to(back_url)) \
              .props('flat color=white round dense')
        ui.label(title).classes('text-h6')


def _not_found(label: str, back_url: str) -> None:
    page_header('Not found', back_url)
    ui.label(f'{label} not found.').classes('text-negative q-pa-md')


def _list_with_placeholder(item_type, adapter, title_field: str, subtitle_fields: list[str],
                           on_select) -> None:
    """ModelList on the left, 'select an item' placeholder on the right (desktop only)."""
    with ui.row().classes('w-full flex-wrap'):
        with ui.column().classes('col-12 col-md-4 q-pa-md'):
            ml = ModelList.from_adapter(item_type, adapter,
                                        title_field=title_field,
                                        subtitle_fields=subtitle_fields)
            ml.on_select(on_select)
            ml.render()
        with ui.column().classes('col-12 col-md-8 q-pa-md flex items-center justify-center'):
            ui.icon('touch_app').classes('text-grey-4 text-h2')
            ui.label('Select an item to edit').classes('text-grey')


# ---------------------------------------------------------------------------
# Level 1 — Project card grid
# ---------------------------------------------------------------------------

@ui.page(R.PATTERN_PROJECTS)
@ui.page('/')
def page_projects() -> None:
    page_header('Projects')
    with ui.grid(columns='repeat(auto-fill, minmax(280px, 1fr))').classes('w-full gap-4 q-pa-md'):
        for key, project in projects_adapter.items():
            with ui.card().classes('cursor-pointer').on(
                    'click', lambda k=key: ui.navigate.to(R.project(k))):
                with ui.card_section():
                    with ui.row().classes('items-center justify-between no-wrap'):
                        ui.label(project.name).classes('text-subtitle1')
                        ui.badge(project.status,
                                 color=_STATUS_COLOR.get(project.status, 'grey'))
                    ui.label(project.description).classes('text-caption text-grey-7 q-mt-xs')


# ---------------------------------------------------------------------------
# Level 2 — Project detail + navigation to sub-collections
# ---------------------------------------------------------------------------

@ui.page(R.PATTERN_PROJECT)
def page_project(pid: str) -> None:
    try:
        project = projects_adapter.read(pid)
    except (KeyError, ValueError):
        _not_found('Project', R.projects())
        return

    page_header(project.name, back_url=R.projects())

    with ui.row().classes('w-full flex-wrap q-pa-md gap-4 items-start'):
        with ui.card().classes('col'):
            _fields_full_width(EditFormWrapper.from_adapter(Project, projects_adapter, pid))

        with ui.card().classes('col-auto'):
            ui.label('Sub-pages').classes('text-subtitle2 q-mb-sm')
            task_count = sum(1 for t in tasks_adapter if t.project_key == pid)
            note_count = sum(1 for n in notes_adapter if n.project_key == pid)
            with ui.column().classes('gap-2'):
                ui.button(f'Tasks ({task_count})', icon='task_alt',
                          on_click=lambda: ui.navigate.to(R.tasks(pid))) \
                  .classes('w-full')
                ui.button(f'Notes ({note_count})', icon='sticky_note_2',
                          on_click=lambda: ui.navigate.to(R.notes(pid))) \
                  .classes('w-full')


# ---------------------------------------------------------------------------
# Level 3 — Task list
# ---------------------------------------------------------------------------

@ui.page(R.PATTERN_TASKS)
def page_tasks(pid: str) -> None:
    try:
        project = projects_adapter.read(pid)
    except (KeyError, ValueError):
        _not_found('Project', R.projects())
        return

    page_header(f'{project.name} – Tasks', back_url=R.project(pid))

    filtered = FilteredAdapter(tasks_adapter,
                               predicate=lambda t: t.project_key == pid,
                               defaults={'project_key': pid})
    _list_with_placeholder(Task, filtered, 'title', ['priority'],
                           on_select=lambda e: ui.navigate.to(R.task(pid, e.row_key)))


# ---------------------------------------------------------------------------
# Level 4 — Task detail
# ---------------------------------------------------------------------------

@ui.page(R.PATTERN_TASK)
def page_task(pid: str, tid: str) -> None:
    try:
        task = tasks_adapter.read(tid)
    except (KeyError, ValueError):
        _not_found('Task', R.tasks(pid))
        return
    if task.project_key != pid:
        _not_found('Task', R.tasks(pid))
        return

    page_header(task.title, back_url=R.tasks(pid))

    with ui.column().classes('q-pa-md w-full max-w-lg'):
        with ui.card().classes('w-full'):
            _fields_full_width(EditFormWrapper.from_adapter(Task, tasks_adapter, tid,
                                                             exclude=['project_key']))


# ---------------------------------------------------------------------------
# Level 3 — Notes list
# ---------------------------------------------------------------------------

@ui.page(R.PATTERN_NOTES)
def page_notes(pid: str) -> None:
    try:
        project = projects_adapter.read(pid)
    except (KeyError, ValueError):
        _not_found('Project', R.projects())
        return

    page_header(f'{project.name} – Notes', back_url=R.project(pid))

    filtered = FilteredAdapter(notes_adapter,
                               predicate=lambda n: n.project_key == pid,
                               defaults={'project_key': pid})
    _list_with_placeholder(Note, filtered, 'text', ['author'],
                           on_select=lambda e: ui.navigate.to(R.note(pid, e.row_key)))


# ---------------------------------------------------------------------------
# Level 4 — Note detail
# ---------------------------------------------------------------------------

@ui.page(R.PATTERN_NOTE)
def page_note(pid: str, nid: str) -> None:
    try:
        note = notes_adapter.read(nid)
    except (KeyError, ValueError):
        _not_found('Note', R.notes(pid))
        return
    if note.project_key != pid:
        _not_found('Note', R.notes(pid))
        return

    page_header('Note', back_url=R.notes(pid))

    with ui.column().classes('q-pa-md w-full max-w-lg'):
        with ui.card().classes('w-full'):
            _fields_full_width(EditFormWrapper.from_adapter(Note, notes_adapter, nid,
                                                             exclude=['project_key']))


ui.run(title='Tree Navigation')
