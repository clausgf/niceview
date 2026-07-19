"""
# Split-Panel Form Navigation

Responsive master-detail navigation around `ModelForm`:

- **Desktop**: a button opens the form in a right-hand panel; a close button hides it.
  Multiple buttons reuse the same panel with different forms.
- **Mobile** (width < 1024px): the same button navigates to a dedicated full-page
  form with a back button.

The forms are plain `ModelForm.from_item()` instances — edits are validated and
written back to the shared Pydantic objects immediately, so no Save button is
needed and both render targets (panel and page) share one renderer function.
"""

from typing import Literal
import pydantic
from nicegui import ui

from niceview import ModelForm


class Settings(pydantic.BaseModel):
    name: str = pydantic.Field(default='My App', max_length=40, title='App name')
    log_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = pydantic.Field(default='INFO', title='Log level')
    debug: bool = pydantic.Field(default=False, title='Debug mode')
    timeout: int = pydantic.Field(default=30, ge=1, le=300, title='Timeout (s)')
    endpoint: str = pydantic.Field(default='https://api.example.com', title='API endpoint')


class Profile(pydantic.BaseModel):
    username: str = pydantic.Field(default='admin', title='Username')
    email: str = pydantic.Field(default='admin@example.com', title='Email')
    role: Literal['Admin', 'Editor', 'Viewer'] = pydantic.Field(default='Admin', title='Role')


settings = Settings()
profile = Profile()

MOBILE_BREAKPOINT = 1024  # px — Quasar's md breakpoint


def render_settings() -> None:
    ModelForm.from_item(settings).render()


def render_profile() -> None:
    ModelForm.from_item(profile).render()


# ---------------------------------------------------------------------------
# Main page  /
# ---------------------------------------------------------------------------

@ui.page('/')
def main_page() -> None:
    with ui.row().classes('w-full flex-wrap'):

        # ── Left / main content — col-md-8 always, col-12 on mobile ──────────
        with ui.column().classes('col-12 col-md-8 q-pa-md'):
            ui.markdown(__doc__ or '')
            ui.separator()

            with ui.card().classes('w-full q-mb-md'):
                ui.label('Status').classes('text-h6')
                ui.label('Everything is running fine.')

            with ui.row().classes('gap-2'):
                ui.button('Settings', icon='settings',
                          on_click=lambda: _open('Settings', render_settings, '/settings'))
                ui.button('Profile', icon='person',
                          on_click=lambda: _open('Profile', render_profile, '/profile'))

        # ── Right / form panel — col-md-4, starts hidden ───────────────────
        with ui.column().classes('col-12 col-md-4 q-pa-md') as panel_col:
            with ui.card().classes('w-full'):
                panel_body = ui.column().classes('w-full')

    panel_col.set_visibility(False)

    async def _open(title: str, render_fn, mobile_url: str) -> None:
        is_mobile = await ui.run_javascript(f'window.innerWidth < {MOBILE_BREAKPOINT}')
        if is_mobile:
            ui.navigate.to(mobile_url)
            return

        panel_col.set_visibility(True)
        panel_body.clear()
        with panel_body:
            with ui.row().classes('w-full justify-between items-center q-mb-sm'):
                ui.label(title).classes('text-h6')
                ui.button(icon='close', on_click=lambda: panel_col.set_visibility(False)) \
                    .props('flat round dense')
            render_fn()


# ---------------------------------------------------------------------------
# Mobile pages
# ---------------------------------------------------------------------------

def _mobile_page(title: str, render_fn) -> None:
    with ui.column().classes('w-full q-pa-md'):
        with ui.row().classes('items-center q-mb-md'):
            ui.button(icon='arrow_back',
                      on_click=lambda: ui.navigate.to('/')).props('flat round dense')
            ui.label(title).classes('text-h6 q-ml-sm')
        with ui.card().classes('w-full'):
            render_fn()


@ui.page('/settings')
def settings_page() -> None:
    _mobile_page('Settings', render_settings)


@ui.page('/profile')
def profile_page() -> None:
    _mobile_page('Profile', render_profile)


ui.run(title='10 — Split-Panel Form Navigation')
