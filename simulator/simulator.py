import os
from nicegui import app, ui

from . import domain as dm
from .SimulationLoop import SimulationLoop


CONFIG_JSON_PATH = os.path.abspath(os.getenv('CONFIG_JSON_PATH', './config.json'))
HIERARCHY_JSON_PATH = os.path.abspath(os.getenv('CONFIG_HIERARCHY_JSON_PATH', './config_hierarchy.json'))
IOT_DEVICE_JSON_PATH = os.path.abspath(os.getenv('CONFIG_IOT_JSON_PATH', './config_iot_devices.json'))
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")


MODE_FIELDS = {
    "fixed": ("value",),
    "vector_custom": ("vector",),
    "vector_uniform": ("vec_min", "vec_max"),
    "fixed_list": ("list",),
    "uniform": ("min", "max"),
    "normal": ("mean", "stddev"),
    "range": ("min", "max", "step"),
    "cycle": ("start",),
}


def generator_modes(data_type: dm.DataType) -> list[str]:
    if data_type == dm.DataType.BOOLEAN:
        return ["fixed", "random_boolean"]
    if data_type == dm.DataType.VECTOR_STRING:
        return ["vector_custom"]
    if data_type in (dm.DataType.VECTOR_INTEGER, dm.DataType.VECTOR_DOUBLE):
        return ["vector_custom", "vector_uniform"]
    if data_type == dm.DataType.STRING:
        return ["fixed_list", "random_string", "api"]
    return ["uniform", "normal", "range", "cycle", "api"]


def build_row(entity: dm.Entity, component: dm.Component, attribute: dm.Attribute, sim: SimulationLoop):
    with ui.row().classes(
            'grid grid-cols-[1.5fr_1.5fr_1.5fr_1.2fr_120px_4fr_120px] items-center gap-4 border-b py-2 w-full font-sans'):

        ui.label(entity.name).classes('text-lg font-bold truncate')
        with ui.column().classes('min-w-0 gap-0'):
            ui.label(component.name).classes('truncate text-slate-700')
            ui.label(f'Device: {component.iotDeviceId}').classes('text-xs text-slate-600 break-all')
            ui.label(f'Type: {component.componentTypeId}').classes('text-xs text-slate-600 break-all')
        ui.label(attribute.name).classes('truncate text-slate-700')
        ui.label(attribute.dataType.value).classes('font-mono text-xs bg-slate-100 p-1 rounded text-center truncate')

        is_running = sim.is_running(attribute.id)
        with ui.column().classes('w-full gap-1'):
            status_label = ui.label('runs' if is_running else 'stopped').classes(
                'w-full text-center text-sm font-medium py-1 px-2 rounded text-white '
                + ('bg-green-500' if is_running else 'bg-red-500')
            ).props('role=status aria-live=polite')
            error_label = ui.label('').classes('text-red-700 text-xs break-all')

        modes = generator_modes(attribute.dataType)
        if attribute.generator_mode is None:
            attribute.generator_mode = modes[0]
        with ui.row().classes('grid grid-cols-4 gap-2 items-center w-full'):
            input_container = ui.row().classes('col-span-3 grid grid-cols-3 gap-1')
            mode_select = ui.select(modes, value=attribute.generator_mode).props('dense outlined')
            mode_select.bind_value(attribute, 'generator_mode')

        def render_fields():
            input_container.clear()
            mode = attribute.generator_mode
            with input_container:
                if mode == 'api':
                    ui.label('Uses Energy Charts renewable-share forecast (Germany)').classes(
                        'text-sm text-slate-600 col-span-3')
                for name in MODE_FIELDS.get(mode, ()):
                    if name == 'value':
                        field = ui.switch('Value', value=False).classes('col-span-3')
                    elif name == 'start':
                        field = ui.number('Start value').props('dense outlined')
                    else:
                        field = ui.input(name).props('dense outlined')
                    field.bind_value(attribute.generator_config, name).bind_enabled_from(mode_select)

        mode_select.on_value_change(render_fields)
        render_fields()

        previous_status = None

        def refresh_status():
            nonlocal previous_status
            running = sim.is_running(attribute.id)
            error = sim.error_for(attribute.id)
            state = (running, error)
            if state == previous_status:
                return
            previous_status = state
            status_label.text = 'runs' if running else ('error' if error else 'stopped')
            status_label.classes(replace=(
                'w-full text-center text-sm font-medium py-1 px-2 rounded text-white '
                + ('bg-green-500' if running else 'bg-red-500')
            ))
            error_label.text = error
            mode_select.set_enabled(not running)

        def toggle():
            if sim.is_running(attribute.id):
                sim.stop_one(attribute)
            else:
                config = attribute.generator_config.copy()
                if config.get('start') in (None, ''):
                    config.pop('start', None)
                sim.start_one(attribute, component.iotDeviceId, config)
            refresh_status()
        ui.button('Start/Stop', on_click=toggle).props('color=primary dense outlined').classes('w-full')
        refresh_status()
        return refresh_status


twin = dm.Twin()
twin.read_from_json(CONFIG_JSON_PATH, IOT_DEVICE_JSON_PATH, HIERARCHY_JSON_PATH)
sim = SimulationLoop(topic=twin.name+"/iot-data", region=AWS_REGION)
app.on_shutdown(sim.stop_all)


@ui.page('/')
def index_page():
    refreshers = []
    with ui.card().classes('w-full p-4 bg-slate-50 mb-4'):
        ui.label(f"Digital Twin Simulation: {twin.name}").classes('text-2xl font-extrabold text-slate-800')

        with ui.row().classes('items-center gap-2'):
            ui.label('SimTime(in sec)')
            def update_interval(e):
                try:
                    sim.sim_time = e.value
                except ValueError as error:
                    e.sender.value = sim.sim_time
                    ui.notify(str(error), type='negative')

            ui.number(value=sim.sim_time, min=0.1, step=0.5,
                      on_change=update_interval).props('dense outlined').classes('w-32')

    for entity, component in twin.components():
        if component.iotDeviceId is None:
            ui.label(
                f'{entity.name} / {component.name}: External type {component.componentTypeId}. '
                'No configured device for simulation.'
            ).classes('text-slate-700 break-all').props('role=status')

    with ui.element('div').classes('w-full overflow-x-auto'):
        with ui.column().classes('w-full min-w-[1100px] gap-0'):
            with ui.row().classes(
                    'grid grid-cols-[1.5fr_1.5fr_1.5fr_1.2fr_120px_4fr_120px] gap-4 font-bold border-b-2 pb-2 mb-2 w-full px-1 text-slate-600 font-sans'):
                ui.label('Entity')
                ui.label('Component')
                ui.label('Attribute')
                ui.label('Datatype')
                ui.label('Status').classes('text-center')
                ui.label('Configuration Parameters')
                ui.label('Action').classes('text-center')

            for entity, component, attribute in twin.flatten():
                refreshers.append(build_row(entity, component, attribute, sim))
    def refresh_rows():
        for refresh in refreshers:
            refresh()

    ui.timer(0.5, refresh_rows)


def main():
    ui.run(host="0.0.0.0", port=5000, reload=False, show=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
