"""User feedback channel page."""

import os
import json
from datetime import datetime
from nicegui import ui
from app.theme import COLORS


FEEDBACK_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'output', 'feedback.json')


def load_feedback():
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, 'r') as f:
            return json.load(f)
    return []


def save_feedback(entries):
    os.makedirs(os.path.dirname(FEEDBACK_FILE), exist_ok=True)
    with open(FEEDBACK_FILE, 'w') as f:
        json.dump(entries, f, indent=2, default=str)


def create_page(api, status_refs):
    """Build the feedback channel page."""

    with ui.row().classes('w-full gap-4'):
        # Left: Submit feedback
        with ui.card().classes('flex-1'):
            ui.label('SUBMIT FEEDBACK').classes('section-title')
            ui.label('Help us improve this tool. Report bugs, suggest features, '
                    'or share your experience.').style(
                f'color: {COLORS["muted"]}; font-size: 13px; margin: 8px 0 16px 0')

            name_input = ui.input('Your Name (optional)').style('width: 100%')
            role_input = ui.select(
                options=['Hydraulic Engineer', 'Civil Engineer', 'Project Manager',
                         'Asset Manager', 'Student', 'Other'],
                label='Your Role',
                value='Hydraulic Engineer',
            ).style('width: 100%')

            category_select = ui.select(
                options=['Bug Report', 'Feature Request', 'Usability Issue',
                         'Data Accuracy', 'Documentation', 'General Feedback'],
                label='Category',
                value='General Feedback',
            ).style('width: 100%')

            severity_select = ui.select(
                options=['Low - Minor inconvenience',
                         'Medium - Affects workflow',
                         'High - Blocks work',
                         'Critical - Wrong results'],
                label='Severity',
                value='Low - Minor inconvenience',
            ).style('width: 100%')

            description_input = ui.textarea(
                'Description',
                placeholder='Describe the issue, feature, or feedback in detail...',
            ).style('width: 100%; min-height: 120px')

            steps_input = ui.textarea(
                'Steps to Reproduce (for bugs)',
                placeholder='1. Open network X\n2. Run analysis\n3. See error...',
            ).style('width: 100%; min-height: 80px')

            def submit_feedback():
                if not description_input.value or not description_input.value.strip():
                    ui.notify('Please enter a description', type='warning')
                    return

                entry = {
                    'id': datetime.now().strftime('%Y%m%d_%H%M%S'),
                    'timestamp': datetime.now().isoformat(),
                    'name': name_input.value or 'Anonymous',
                    'role': role_input.value,
                    'category': category_select.value,
                    'severity': severity_select.value,
                    'description': description_input.value,
                    'steps_to_reproduce': steps_input.value or '',
                    'status': 'Open',
                }

                entries = load_feedback()
                entries.append(entry)
                save_feedback(entries)

                # Clear form
                description_input.value = ''
                steps_input.value = ''
                name_input.value = ''

                ui.notify('Feedback submitted - thank you!', type='positive')
                refresh_history()

            ui.button('Submit Feedback', on_click=submit_feedback).props(
                'color=positive').style('margin-top: 12px')

        # Right: Feedback history
        with ui.card().classes('flex-1'):
            ui.label('FEEDBACK HISTORY').classes('section-title')
            history_container = ui.column().style(
                'max-height: 600px; overflow-y: auto; width: 100%')

            def refresh_history():
                history_container.clear()
                entries = load_feedback()
                with history_container:
                    if not entries:
                        ui.label('No feedback submitted yet').style(
                            f'color: {COLORS["muted"]}; font-size: 13px')
                        return

                    for entry in reversed(entries):
                        cat = entry.get('category', 'General')
                        sev = entry.get('severity', 'Low')
                        status = entry.get('status', 'Open')

                        if 'Critical' in sev or 'High' in sev:
                            border_color = COLORS['red']
                        elif 'Medium' in sev:
                            border_color = COLORS['orange']
                        else:
                            border_color = COLORS['accent']

                        with ui.card().style(
                            f'width: 100%; border-left: 3px solid {border_color}; '
                            f'margin-bottom: 8px; padding: 10px'):

                            with ui.row().classes('items-center gap-2'):
                                # Status badge
                                status_color = COLORS['green'] if status == 'Resolved' else (
                                    COLORS['orange'] if status == 'In Progress' else COLORS['muted'])
                                ui.label(status).style(
                                    f'background: {status_color}20; color: {status_color}; '
                                    f'padding: 1px 8px; border-radius: 3px; font-size: 10px; '
                                    f'font-weight: 700')
                                ui.label(cat).style(
                                    f'background: {COLORS["accent"]}20; color: {COLORS["accent"]}; '
                                    f'padding: 1px 8px; border-radius: 3px; font-size: 10px')
                                ui.label(entry.get('timestamp', '')[:10]).style(
                                    f'color: {COLORS["muted"]}; font-size: 10px; margin-left: auto')

                            ui.label(entry.get('description', '')[:200]).style(
                                f'color: {COLORS["text"]}; font-size: 12px; margin-top: 4px')

                            with ui.row().classes('items-center gap-2').style('margin-top: 4px'):
                                ui.label(f'By: {entry.get("name", "Anonymous")}').style(
                                    f'color: {COLORS["muted"]}; font-size: 10px')
                                ui.label(f'Role: {entry.get("role", "")}').style(
                                    f'color: {COLORS["muted"]}; font-size: 10px')
                                ui.label(sev.split(' - ')[0]).style(
                                    f'color: {border_color}; font-size: 10px; font-weight: 600')

            refresh_history()
