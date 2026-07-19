"""
Demo pages used to generate the README screenshots (see capture.py).

Not part of the numbered examples: a single NiceGUI app with three routes
(/hero, /grid, /drilldown) built from one deliberately varied model so the
screenshots show more than plain text inputs. Run indirectly via capture.py.
"""
from typing import Annotated, Literal

import pydantic
from nicegui import ui

import niceview
from niceview import DrillDownWrapper, EditGridWrapper, ModelForm

# Crisp "app-like" look for every widget on every page (also the drill-down
# detail form, which is rendered lazily on navigation): outlined + dense, full
# width, and hide-bottom-space to drop the reserved error line so fields sit
# tightly together.
for _el in (ui.input, ui.number, ui.select, ui.textarea):
    _el.default_props('outlined dense hide-bottom-space')
    _el.default_classes('w-full')


class Deployment(pydantic.BaseModel):
    name: str = pydantic.Field(default='api-gateway', max_length=40, title='Service name')
    environment: Literal['dev', 'staging', 'production'] = pydantic.Field(default='production', title='Environment')
    strategy: Annotated[
        Literal['rolling', 'recreate', 'blue-green'],
        niceview.Field(widget_type='ui.toggle', label='Rollout strategy'),
    ] = 'blue-green'
    replicas: int = pydantic.Field(default=4, ge=0, le=20, title='Replicas')
    memory_mb: Annotated[
        int,
        pydantic.Field(default=4096, ge=256, le=8192, title='Memory (MB)'),
        niceview.Field(widget_type='ui.slider', step=256),
    ] = 4096
    autoscale: bool = pydantic.Field(default=True, title='Autoscale')
    regions: Annotated[
        list[Literal['us', 'eu', 'apac']],
        niceview.Field(props='use-chips', label='Regions'),
    ] = pydantic.Field(default_factory=lambda: ['eu', 'us'])  # type: ignore[arg-type]
    accent: Annotated[str, niceview.Field(widget_type='ui.color_input', label='Accent color')] = '#4a90e2'
    notes: Annotated[str, niceview.Field(widget_type='ui.textarea', label='Notes')] = 'Blue-green rollout for zero-downtime deploys.'

    def __str__(self) -> str:
        return self.name


def _sample() -> list[Deployment]:
    return [
        Deployment(name='api-gateway', environment='production', replicas=4),
        Deployment(name='web-frontend', environment='staging', replicas=2, autoscale=False),
        Deployment(name='worker', environment='production', replicas=6),
        Deployment(name='cron-runner', environment='dev', replicas=1, autoscale=False),
    ]


@ui.page('/hero')
def hero() -> None:
    ui.query('body').style('background: #eef0f4')
    with ui.column().classes('w-full items-center q-pa-lg'):
        with ui.card().classes('shot-card w-full max-w-md'):
            ui.label('Deployment').classes('text-h6')
            ModelForm.from_item(Deployment()).render()


@ui.page('/grid')
def grid() -> None:
    ui.query('body').style('background: #eef0f4')
    with ui.column().classes('w-full items-center q-pa-lg'):
        with ui.card().classes('shot-card w-full max-w-2xl'):
            wrapper = EditGridWrapper.from_list(
                Deployment, _sample(),
                include=['name', 'environment', 'replicas', 'autoscale'],
                title='Deployments',
            ).render()
            wrapper.grid.widget.classes('w-full')


def _compact_detail(adapter, key, set_key) -> None:  # noqa: ANN001
    ModelForm.from_adapter(
        Deployment, adapter, key, autosave=True,
        include=['name', 'environment', 'strategy', 'autoscale'],
    ).render()


@ui.page('/drilldown')
def drilldown() -> None:
    ui.query('body').style('background: #eef0f4')
    with ui.column().classes('w-full items-center q-pa-lg'):
        with ui.card().classes('shot-card w-full max-w-sm'):
            DrillDownWrapper.from_list(
                Deployment, _sample(),
                list_title='Deployments',
                item_title_field='name',
                item_subtitle_fields=['environment'],
                render_detail=_compact_detail,
            ).render()


ui.run(port=8137, show=False, reload=False, title='NiceView screenshots')
