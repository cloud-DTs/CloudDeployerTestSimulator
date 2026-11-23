import asyncio
import importlib
import json
from pathlib import Path
from unittest.mock import patch

from nicegui import ui
from nicegui.testing import user_simulation


async def open_device_rows(user):
    await user.open("/")
    buttons = sorted(user.find("Start/Stop").elements, key=lambda button: button.id)
    for button, name in zip(buttons, ("first", "alias", "other_device"), strict=True):
        button.parent_slot.parent.mark(name)


def control_value(user, kind, label=None):
    control, = user.find(kind=kind, content=label).elements
    return control.value


def test_aliases_share_generator_controls_and_restart_settings(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    example = root / "input" / "shared-component-type"
    hierarchy = json.loads((example / "config_hierarchy.json").read_text(encoding="utf-8"))
    children = hierarchy[0]["children"]
    children.insert(1, {**children[0], "name": "Alias_A"})
    hierarchy_path = tmp_path / "hierarchy.json"
    hierarchy_path.write_text(json.dumps(hierarchy), encoding="utf-8")
    monkeypatch.setenv("CONFIG_JSON_PATH", str(example / "config.json"))
    monkeypatch.setenv("CONFIG_IOT_JSON_PATH", str(example / "config_iot_devices.json"))
    monkeypatch.setenv("CONFIG_HIERARCHY_JSON_PATH", str(hierarchy_path))
    monkeypatch.setenv("SIMULATOR_MOCK_AWS", "true")

    async def check_controls():
        async with user_simulation(main_file=root / "main.py") as user:
            await open_device_rows(user)
            sim = importlib.import_module("simulator.simulator").sim
            with patch.object(sim, "start_one", wraps=sim.start_one) as start:
                with user.scope(marker="first"):
                    user.find(kind=ui.input, content="min").type("42")
                    user.find(kind=ui.input, content="max").type("42")
                    user.find("Start/Stop").click()
                with user.scope(marker="alias"):
                    assert control_value(user, ui.input, "min") == "42"
                    assert control_value(user, ui.input, "max") == "42"
                    user.find("Start/Stop").click()
                    user.find("Start/Stop").click()
                assert [call.args[2] for call in start.call_args_list] == [
                    {"mode": "uniform", "min": "42", "max": "42"},
                    {"mode": "uniform", "min": "42", "max": "42"},
                ]

                await open_device_rows(user)
                with user.scope(marker="alias"):
                    assert control_value(user, ui.input, "max") == "42"
                    user.find("Start/Stop").click()
                    user.find(ui.select).click()
                    user.find("range").click()
                    user.find(kind=ui.input, content="step").type("2")
                with user.scope(marker="first"):
                    assert control_value(user, ui.select) == "range"
                    assert control_value(user, ui.input, "step") == "2"
                    user.find("Start/Stop").click()
                assert start.call_args.args[2] == {"mode": "range", "min": "", "max": "", "step": "2"}
                with user.scope(marker="other_device"):
                    assert control_value(user, ui.select) == "uniform"
                    assert control_value(user, ui.input, "min") == ""

    asyncio.run(check_controls())
