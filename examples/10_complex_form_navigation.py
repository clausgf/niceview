"""
Example 10 – Complex form via page navigation (pure NiceGUI).

Pattern for forms too complex for a dialog:
- Desktop: split panel — content left, form always visible right
- Mobile:  button on main page navigates to a dedicated form page

The form is defined once (_render_form) and reused in both layouts.
Shared state is a plain dict here; swap in any adapter for real use.
"""
from nicegui import ui

# ---------------------------------------------------------------------------
# Shared state (replace with JsonAdapter / SqlModelAdapter in production)
# ---------------------------------------------------------------------------

settings: dict = {
    'name': 'My App',
    'description': '',
    'debug': False,
    'log_level': 'INFO',
    'timeout': 30,
    'retries': 3,
    'endpoint': 'https://api.example.com',
    'api_key': '',
}


# ---------------------------------------------------------------------------
# Reusable form (same markup on both pages)
# ---------------------------------------------------------------------------

def _render_form() -> None:
    with ui.card().classes('w-full'):
        ui.label('Settings').classes('text-h6 q-mb-md')

        with ui.column().classes('w-full gap-2'):
            ui.input('App name', value=settings['name']) \
                .bind_value(settings, 'name')
            ui.textarea('Description', value=settings['description']) \
                .bind_value(settings, 'description')

            ui.separator()

            ui.select(['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                      label='Log level', value=settings['log_level']) \
                .bind_value(settings, 'log_level')
            ui.switch('Debug mode').bind_value(settings, 'debug')

            ui.separator()

            ui.number('Timeout (s)', value=settings['timeout'], min=1, max=300) \
                .bind_value(settings, 'timeout')
            ui.number('Retries', value=settings['retries'], min=0, max=10) \
                .bind_value(settings, 'retries')
            ui.input('API endpoint', value=settings['endpoint']) \
                .bind_value(settings, 'endpoint')
            ui.input('API key', password=True, password_toggle_button=True,
                     value=settings['api_key']) \
                .bind_value(settings, 'api_key')

        with ui.row().classes('w-full justify-end q-mt-md'):
            ui.button('Save', icon='save', color='primary',
                      on_click=lambda: ui.notify('Saved', color='positive'))


# ---------------------------------------------------------------------------
# Main page  /
# ---------------------------------------------------------------------------

@ui.page('/')
def main_page() -> None:
    with ui.row().classes('w-full flex-wrap'):

        # ── Left / main content (always visible) ───────────────────────────
        with ui.column().classes('col-12 col-md-8 q-pa-md'):
            ui.label('Dashboard').classes('text-h4 q-mb-lg')

            with ui.card().classes('w-full q-mb-md'):
                ui.label('Status').classes('text-h6')
                ui.label('Everything is running fine.')

            # Button only visible on mobile (desktop shows the right panel)
            ui.button('Open Settings', icon='settings',
                      on_click=lambda: ui.navigate.to('/settings')) \
                .classes('lt-md')

        # ── Right / form panel (desktop only) ──────────────────────────────
        with ui.column().classes('col-4 gt-sm q-pa-md'):
            _render_form()


# ---------------------------------------------------------------------------
# Settings page  /settings  (mobile full-page view)
# ---------------------------------------------------------------------------

@ui.page('/settings')
def settings_page() -> None:
    # Back button — only shown on mobile; on desktop this URL is never reached
    with ui.row().classes('items-center q-pa-sm lt-md'):
        ui.button(icon='arrow_back',
                  on_click=lambda: ui.navigate.to('/')) \
            .props('flat round dense')
        ui.label('Settings').classes('text-h6 q-ml-sm')

    with ui.column().classes('w-full q-pa-md'):
        _render_form()


ui.run(title='Complex Form Navigation')
