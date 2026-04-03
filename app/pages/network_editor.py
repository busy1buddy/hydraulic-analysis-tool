"""
Interactive Network Editor Page
================================
Allows users to view, select, edit, and create network elements
directly in the dashboard. Uses Plotly for visualization with
click event handling via NiceGUI.
"""

import os
import plotly.graph_objects as go
from nicegui import ui
from app.theme import PLOTLY_LAYOUT, COLORS, CHART_COLORS
from app.components.network_plot import create_network_figure
import wntr


def create_page(api, status_refs):
    """Build the network editor page."""

    editor_state = {
        'selected_element': None,
        'selected_type': None,  # 'junction', 'pipe', 'reservoir', 'tank'
        'mode': 'select',  # 'select', 'add_junction', 'add_pipe'
        'pipe_start': None,  # for add_pipe mode
    }

    # --- Controls ---
    with ui.card().classes('w-full').style('margin-bottom: 16px'):
        ui.label('NETWORK EDITOR').classes('section-title')
        with ui.row().classes('items-center gap-3 flex-wrap').style('margin-top: 8px'):
            network_select = ui.select(
                options=api.list_networks(), label='Network',
                value=api.list_networks()[0] if api.list_networks() else None,
            ).style('min-width: 200px')

            ui.button('Load', on_click=lambda: load_network()).props('color=primary')
            ui.separator().props('vertical')

            mode_toggle = ui.toggle(
                {
                    'select': 'Select / Edit',
                    'add_junction': 'Add Junction',
                    'add_pipe': 'Add Pipe',
                },
                value='select',
                on_change=lambda e: set_mode(e.value),
            )
            ui.separator().props('vertical')

            ui.button('Save Network', on_click=lambda: save_network()).props(
                'color=positive outline')
            ui.button('Delete Selected', on_click=lambda: delete_selected()).props(
                'color=negative outline')

    with ui.row().classes('w-full gap-4'):
        # Left: Network canvas
        with ui.card().style('flex: 2'):
            ui.label('NETWORK CANVAS').classes('section-title')
            with ui.row().classes('items-center gap-2').style('margin-bottom: 8px'):
                mode_label = ui.label('Mode: Select / Edit').style(
                    f'color: {COLORS["muted"]}; font-size: 12px')
                instruction_label = ui.label('Click a node or pipe to select it').style(
                    f'color: {COLORS["cyan"]}; font-size: 12px')

            network_chart = ui.plotly({}).style('height: 500px')

        # Right: Properties panel
        with ui.card().style('flex: 1; min-width: 280px'):
            ui.label('ELEMENT PROPERTIES').classes('section-title')
            props_container = ui.column().style('width: 100%')
            with props_container:
                ui.label('Select an element to view its properties').style(
                    f'color: {COLORS["muted"]}; font-size: 13px')

    # --- Add junction dialog ---
    with ui.dialog() as add_junc_dialog, ui.card().style('min-width: 300px'):
        ui.label('Add New Junction').style('font-size: 16px; font-weight: 600')
        junc_id_input = ui.input('Junction ID', value='').style('width: 100%')
        junc_elev_input = ui.number('Elevation (m)', value=40).style('width: 100%')
        junc_demand_input = ui.number('Demand (LPS)', value=0).style('width: 100%')
        junc_x_input = ui.number('X Coordinate', value=0).style('width: 100%')
        junc_y_input = ui.number('Y Coordinate', value=0).style('width: 100%')

        with ui.row().classes('justify-end gap-2').style('margin-top: 12px'):
            ui.button('Cancel', on_click=add_junc_dialog.close).props('flat')
            ui.button('Add', on_click=lambda: confirm_add_junction()).props('color=primary')

    # --- Add pipe dialog ---
    with ui.dialog() as add_pipe_dialog, ui.card().style('min-width: 300px'):
        ui.label('Add New Pipe').style('font-size: 16px; font-weight: 600')
        pipe_id_input = ui.input('Pipe ID', value='').style('width: 100%')
        pipe_start_input = ui.input('Start Node', value='').style('width: 100%')
        pipe_end_input = ui.input('End Node', value='').style('width: 100%')
        pipe_length_input = ui.number('Length (m)', value=100).style('width: 100%')
        pipe_dia_input = ui.number('Diameter (mm)', value=200).style('width: 100%')
        pipe_rough_input = ui.number('Roughness (C)', value=130).style('width: 100%')

        with ui.row().classes('justify-end gap-2').style('margin-top: 12px'):
            ui.button('Cancel', on_click=add_pipe_dialog.close).props('flat')
            ui.button('Add', on_click=lambda: confirm_add_pipe()).props('color=primary')

    def set_mode(mode):
        editor_state['mode'] = mode
        labels = {
            'select': ('Mode: Select / Edit', 'Click a node or pipe to select it'),
            'add_junction': ('Mode: Add Junction', 'Click canvas to place, or use dialog'),
            'add_pipe': ('Mode: Add Pipe', 'Enter start/end nodes in dialog'),
        }
        mode_label.set_text(labels[mode][0])
        instruction_label.set_text(labels[mode][1])

        if mode == 'add_junction':
            # Auto-generate next ID
            existing = list(api.wn.junction_name_list) if api.wn else []
            nums = [int(j[1:]) for j in existing if j[1:].isdigit()]
            next_num = max(nums, default=0) + 1
            junc_id_input.value = f'J{next_num}'
            add_junc_dialog.open()

        elif mode == 'add_pipe':
            existing = list(api.wn.pipe_name_list) if api.wn else []
            nums = [int(p[1:]) for p in existing if p[1:].isdigit()]
            next_num = max(nums, default=0) + 1
            pipe_id_input.value = f'P{next_num}'
            add_pipe_dialog.open()

    def load_network():
        fname = network_select.value
        if not fname:
            return
        try:
            api.load_network(fname)
            status_refs['network'].set_text(fname)
            refresh_canvas()
            ui.notify(f'Loaded {fname}', type='positive')
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def refresh_canvas():
        if api.wn is None:
            return
        fig = create_network_figure(api.wn)
        fig.update_layout(dragmode='pan')
        network_chart.update_figure(fig)

    def select_element(element_id, element_type):
        editor_state['selected_element'] = element_id
        editor_state['selected_type'] = element_type
        show_properties(element_id, element_type)

    def show_properties(element_id, element_type):
        props_container.clear()
        if api.wn is None:
            return

        with props_container:
            ui.label(f'{element_type.upper()}: {element_id}').style(
                f'font-size: 16px; font-weight: 600; color: {COLORS["text"]}')
            ui.separator()

            if element_type == 'junction':
                node = api.wn.get_node(element_id)
                elev_input = ui.number('Elevation (m)',
                                      value=round(node.elevation, 1))
                demand_val = node.demand_timeseries_list[0].base_value * 1000 if node.demand_timeseries_list else 0
                demand_input = ui.number('Demand (LPS)',
                                        value=round(demand_val, 2))
                x_input = ui.number('X', value=round(node.coordinates[0], 1))
                y_input = ui.number('Y', value=round(node.coordinates[1], 1))

                def save_junction():
                    node.elevation = float(elev_input.value)
                    if node.demand_timeseries_list:
                        node.demand_timeseries_list[0].base_value = float(demand_input.value) / 1000
                    node.coordinates = (float(x_input.value), float(y_input.value))
                    refresh_canvas()
                    ui.notify(f'{element_id} updated', type='positive')

                ui.button('Apply Changes', on_click=save_junction).props(
                    'color=primary').style('margin-top: 12px')

            elif element_type == 'pipe':
                pipe = api.wn.get_link(element_id)
                ui.label(f'From: {pipe.start_node_name}').style(
                    f'color: {COLORS["muted"]}')
                ui.label(f'To: {pipe.end_node_name}').style(
                    f'color: {COLORS["muted"]}')
                len_input = ui.number('Length (m)',
                                     value=round(pipe.length, 1))
                dia_input = ui.number('Diameter (mm)',
                                     value=round(pipe.diameter * 1000))
                rough_input = ui.number('Roughness (C)',
                                       value=round(pipe.roughness))

                def save_pipe():
                    pipe.length = float(len_input.value)
                    pipe.diameter = float(dia_input.value) / 1000
                    pipe.roughness = float(rough_input.value)
                    refresh_canvas()
                    ui.notify(f'{element_id} updated', type='positive')

                ui.button('Apply Changes', on_click=save_pipe).props(
                    'color=primary').style('margin-top: 12px')

            elif element_type == 'reservoir':
                node = api.wn.get_node(element_id)
                head_input = ui.number('Head (m)',
                                      value=round(node.base_head, 1))

                def save_reservoir():
                    node.base_head = float(head_input.value)
                    refresh_canvas()
                    ui.notify(f'{element_id} updated', type='positive')

                ui.button('Apply Changes', on_click=save_reservoir).props(
                    'color=primary').style('margin-top: 12px')

    def confirm_add_junction():
        try:
            jid = junc_id_input.value.strip()
            api.wn.add_junction(
                jid,
                elevation=float(junc_elev_input.value),
                base_demand=float(junc_demand_input.value) / 1000,
                coordinates=(float(junc_x_input.value), float(junc_y_input.value)),
            )
            add_junc_dialog.close()
            refresh_canvas()
            select_element(jid, 'junction')
            ui.notify(f'Added junction {jid}', type='positive')
            mode_toggle.value = 'select'
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def confirm_add_pipe():
        try:
            pid = pipe_id_input.value.strip()
            api.wn.add_pipe(
                pid,
                pipe_start_input.value.strip(),
                pipe_end_input.value.strip(),
                length=float(pipe_length_input.value),
                diameter=float(pipe_dia_input.value) / 1000,
                roughness=float(pipe_rough_input.value),
            )
            add_pipe_dialog.close()
            refresh_canvas()
            select_element(pid, 'pipe')
            ui.notify(f'Added pipe {pid}', type='positive')
            mode_toggle.value = 'select'
        except Exception as e:
            ui.notify(f'Error: {e}', type='negative')

    def delete_selected():
        elem = editor_state['selected_element']
        etype = editor_state['selected_type']
        if not elem or not api.wn:
            ui.notify('Nothing selected', type='warning')
            return

        try:
            if etype in ('junction', 'reservoir', 'tank'):
                api.wn.remove_node(elem)
            elif etype in ('pipe', 'valve'):
                api.wn.remove_link(elem)

            editor_state['selected_element'] = None
            props_container.clear()
            with props_container:
                ui.label('Element deleted').style(f'color: {COLORS["muted"]}')
            refresh_canvas()
            ui.notify(f'Deleted {etype} {elem}', type='info')
        except Exception as e:
            ui.notify(f'Cannot delete: {e}', type='negative')

    def save_network():
        if api.wn is None:
            ui.notify('No network loaded', type='warning')
            return
        fname = network_select.value
        if not fname:
            return
        try:
            path = os.path.join(api.model_dir, fname)
            wntr.network.write_inpfile(api.wn, path)
            ui.notify(f'Saved to {fname}', type='positive')
        except Exception as e:
            ui.notify(f'Save failed: {e}', type='negative')

    # Element selector - since Plotly click events are complex in NiceGUI,
    # provide a dropdown-based selector as the primary selection method
    with ui.card().classes('w-full').style('margin-top: 16px'):
        ui.label('ELEMENT SELECTOR').classes('section-title')
        ui.label('Select an element to view and edit its properties:').style(
            f'color: {COLORS["muted"]}; font-size: 12px')

        with ui.row().classes('items-center gap-3 flex-wrap').style('margin-top: 8px'):
            element_type_select = ui.select(
                options=['Junctions', 'Pipes', 'Reservoirs', 'Tanks', 'Valves'],
                label='Element Type', value='Junctions',
            ).style('min-width: 150px')

            element_id_select = ui.select(
                options=[], label='Element ID',
            ).style('min-width: 150px')

            ui.button('Select', on_click=lambda: on_element_select()).props('color=primary')

        def update_element_list(e=None):
            if api.wn is None:
                return
            t = element_type_select.value
            if t == 'Junctions':
                element_id_select.options = list(api.wn.junction_name_list)
            elif t == 'Pipes':
                element_id_select.options = list(api.wn.pipe_name_list)
            elif t == 'Reservoirs':
                element_id_select.options = list(api.wn.reservoir_name_list)
            elif t == 'Tanks':
                element_id_select.options = list(api.wn.tank_name_list)
            elif t == 'Valves':
                element_id_select.options = list(api.wn.valve_name_list)
            element_id_select.update()

        element_type_select.on_value_change(update_element_list)

        def on_element_select():
            eid = element_id_select.value
            if not eid:
                return
            t = element_type_select.value.lower().rstrip('s')
            if t == 'valve':
                t = 'valve'
            select_element(eid, t)

    # Auto-load first network
    if api.list_networks():
        ui.timer(0.5, lambda: load_network(), once=True)
        ui.timer(1.0, lambda: update_element_list(), once=True)
