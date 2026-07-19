"""
# Multi-Level Tree Navigation

URL-addressable drill-down over three levels with explicit back buttons:

Level 1  `/projects`                   Card grid of all projects
Level 2  `/projects/{pid}`             Edit project + button to the task list
Level 3  `/projects/{pid}/tasks`       Task list (`ModelList`, `profile='summary'`)
Level 4  `/projects/{pid}/tasks/{tid}` Task detail form (`profile='detail'`)

Patterns shown:
- **URL factory `R`**: every URL pattern lives in one place; pages register with
  `@ui.page(R.TASK)` and navigate with `R.TASK.format(...)` — changing a URL is a
  one-line edit.
- **`FilteredAdapter`**: the task list is a parent-filtered view of one global
  adapter; `defaults=` stamps new tasks with the current project key.
- **`Meta.profiles`**: the same `Task` model renders as a compact list
  (`'summary'`) and as a full detail form (`'detail'`, hiding `project_key`)
  without repeating `include=`/`exclude=` at every call site.

Further sub-collections (notes, files, ...) repeat the Level-3/4 pattern.
Replace the in-memory `ListAdapter`s with `JsonListAdapter` or `SqlModelAdapter`
for persistence without changing any page logic.
"""

from typing import Literal
from nicegui import ui
from pydantic import BaseModel, Field

from niceview import ListAdapter, FilteredAdapter, ModelList, EditFormWrapper


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

    class Meta:
        profiles = {
            'summary': ['title', 'priority'],           # list view: title + subtitle
            'detail': ['title', 'priority', 'done'],    # form view: everything but project_key
        }

    def __str__(self) -> str:
        return self.title


# ---------------------------------------------------------------------------
# In-memory storage
# ListAdapter assigns sequential keys: first project → "0", second → "1", …
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
    Task(project_key='0', title='Create wireframes',   priority='high',   done=True),
    Task(project_key='0', title='Implement homepage',  priority='high',   done=False),
    Task(project_key='0', title='Write tests',         priority='medium', done=False),
    Task(project_key='1', title='Define requirements', priority='high',   done=True),
    Task(project_key='1', title='Setup CI/CD',         priority='medium', done=False),
])


# ---------------------------------------------------------------------------
# URL patterns — single source of truth: register with @ui.page(R.X),
# navigate with R.X.format(pid=..., tid=...)
# ---------------------------------------------------------------------------

class R:
    PROJECTS = '/projects'
    PROJECT  = '/projects/{pid}'
    TASKS    = '/projects/{pid}/tasks'
    TASK     = '/projects/{pid}/tasks/{tid}'


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


# ---------------------------------------------------------------------------
# Level 1 — Project card grid
# ---------------------------------------------------------------------------

@ui.page(R.PROJECTS)
@ui.page('/')
def page_projects() -> None:
    page_header('Projects')
    with ui.grid(columns='repeat(auto-fill, minmax(280px, 1fr))').classes('w-full gap-4 q-pa-md'):
        for key, project in projects_adapter.items():
            with ui.card().classes('cursor-pointer').on(
                    'click', lambda k=key: ui.navigate.to(R.PROJECT.format(pid=k))):
                with ui.card_section():
                    with ui.row().classes('items-center justify-between no-wrap'):
                        ui.label(project.name).classes('text-subtitle1')
                        ui.badge(project.status,
                                 color=_STATUS_COLOR.get(project.status, 'grey'))
                    ui.label(project.description).classes('text-caption text-grey-7 q-mt-xs')


# ---------------------------------------------------------------------------
# Level 2 — Project detail + navigation to the task list
# ---------------------------------------------------------------------------

@ui.page(R.PROJECT)
def page_project(pid: str) -> None:
    try:
        project = projects_adapter.read(pid)
    except (KeyError, ValueError):
        _not_found('Project', R.PROJECTS)
        return

    page_header(project.name, back_url=R.PROJECTS)

    with ui.row().classes('w-full flex-wrap q-pa-md gap-4 items-start'):
        with ui.card().classes('col'):
            _fields_full_width(EditFormWrapper.from_adapter(Project, projects_adapter, pid).render())

        with ui.card().classes('col-auto'):
            task_count = sum(1 for t in tasks_adapter if t.project_key == pid)
            ui.button(f'Tasks ({task_count})', icon='task_alt',
                      on_click=lambda: ui.navigate.to(R.TASKS.format(pid=pid))) \
              .classes('w-full')


# ---------------------------------------------------------------------------
# Level 3 — Task list (parent-filtered, profile='summary')
# ---------------------------------------------------------------------------

@ui.page(R.TASKS)
def page_tasks(pid: str) -> None:
    try:
        project = projects_adapter.read(pid)
    except (KeyError, ValueError):
        _not_found('Project', R.PROJECTS)
        return

    page_header(f'{project.name} – Tasks', back_url=R.PROJECT.format(pid=pid))

    filtered = FilteredAdapter(tasks_adapter,
                               predicate=lambda t: t.project_key == pid,
                               defaults={'project_key': pid})
    with ui.column().classes('col-12 col-md-4 q-pa-md'):
        ml = ModelList.from_adapter(Task, filtered, profile='summary')
        ml.on_select(lambda e: ui.navigate.to(R.TASK.format(pid=pid, tid=e.row_key)))
        ml.render()


# ---------------------------------------------------------------------------
# Level 4 — Task detail (profile='detail' hides project_key)
# ---------------------------------------------------------------------------

@ui.page(R.TASK)
def page_task(pid: str, tid: str) -> None:
    try:
        task = tasks_adapter.read(tid)
    except (KeyError, ValueError):
        _not_found('Task', R.TASKS.format(pid=pid))
        return
    if task.project_key != pid:
        _not_found('Task', R.TASKS.format(pid=pid))
        return

    page_header(task.title, back_url=R.TASKS.format(pid=pid))

    with ui.column().classes('q-pa-md w-full max-w-lg'):
        with ui.card().classes('w-full'):
            _fields_full_width(EditFormWrapper.from_adapter(Task, tasks_adapter, tid,
                                                            profile='detail').render())


ui.run(title='11 — Tree Navigation')
