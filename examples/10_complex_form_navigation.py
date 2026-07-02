"""
Example 10 – Complex form via split-panel (pure NiceGUI).

- Desktop: button opens a right panel; close button hides it.
           Multiple buttons → different forms in the same panel.
- Mobile:  button navigates to a dedicated full-page form.
           Back button returns to main.
"""
from nicegui import ui

# ---------------------------------------------------------------------------
# Shared state (replace with JsonAdapter / SqlModelAdapter in production)
# ---------------------------------------------------------------------------

settings = {
    'name': 'My App', 'debug': False,
    'log_level': 'INFO', 'timeout': 30, 'endpoint': 'https://api.example.com',
}
profile = {'username': 'admin', 'email': 'admin@example.com', 'role': 'Admin'}

MOBILE_BREAKPOINT = 1024  # px — Quasar's md breakpoint


# ---------------------------------------------------------------------------
# Form renderers  (reused on desktop panel and mobile pages)
# ---------------------------------------------------------------------------

def render_settings() -> None:
    ui.input('App name').bind_value(settings, 'name')
    ui.select(['DEBUG', 'INFO', 'WARNING', 'ERROR'],
              label='Log level').bind_value(settings, 'log_level')
    ui.switch('Debug mode').bind_value(settings, 'debug')
    ui.number('Timeout (s)', min=1, max=300).bind_value(settings, 'timeout')
    ui.input('API endpoint').bind_value(settings, 'endpoint')
    with ui.row().classes('justify-end w-full q-mt-md'):
        ui.button('Save', icon='save', color='primary',
                  on_click=lambda: ui.notify('Saved', color='positive'))


def render_profile() -> None:
    ui.input('Username').bind_value(profile, 'username')
    ui.input('Email').bind_value(profile, 'email')
    ui.select(['Admin', 'Editor', 'Viewer'],
              label='Role').bind_value(profile, 'role')
    with ui.row().classes('justify-end w-full q-mt-md'):
        ui.button('Save', icon='save', color='primary',
                  on_click=lambda: ui.notify('Saved', color='positive'))


# ---------------------------------------------------------------------------
# Main page  /
# ---------------------------------------------------------------------------

@ui.page('/')
def main_page() -> None:

    with ui.row().classes('w-full flex-wrap') as root_row:

        # ── Left / main content ─────────────────────────────────────────────
        with ui.column().classes('col-12 q-pa-md') as left_col:

            ui.label('Dashboard').classes('text-h4 q-mb-lg')

            with ui.card().classes('w-full q-mb-md'):
                ui.label('Status').classes('text-h6')
                ui.label('Everything is running fine.')

            with ui.row().classes('gap-2'):
                ui.button('Settings', icon='settings',
                          on_click=lambda: _open('Settings', render_settings, '/settings'))
                ui.button('Profile', icon='person',
                          on_click=lambda: _open('Profile', render_profile, '/profile'))

        # ── Right / form panel (starts hidden) ─────────────────────────────
        with ui.column().classes('col-12 col-md-4 q-pa-md') as panel_col:
            with ui.card().classes('w-full'):
                panel_body = ui.column().classes('w-full')

    panel_col.set_visibility(False)

    # ── Panel logic ─────────────────────────────────────────────────────────

    def _hide_panel() -> None:
        panel_col.set_visibility(False)
        left_col.classes(remove='col-md-8')          # back to full width

    async def _open(title: str, render_fn, mobile_url: str) -> None:
        is_mobile = await ui.run_javascript(
            f'window.innerWidth < {MOBILE_BREAKPOINT}')
        if is_mobile:
            ui.navigate.to(mobile_url)
            return

        left_col.classes(add='col-md-8')             # shrink to make room
        panel_col.set_visibility(True)
        panel_body.clear()
        with panel_body:
            with ui.row().classes('w-full justify-between items-center q-mb-sm'):
                ui.label(title).classes('text-h6')
                ui.button(icon='close', on_click=_hide_panel) \
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


ui.run(title='Complex Form — Split Panel')
