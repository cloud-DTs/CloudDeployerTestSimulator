import asyncio
import sys
from pathlib import Path

from nicegui.testing import user_simulation


def test_twin_directory_overrides_file_paths_and_serves_microgrid(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    monkeypatch.setattr(sys, "argv", ["main.py", "--twin_dir", str(root / "input")])
    for variable in ("CONFIG_JSON_PATH", "CONFIG_HIERARCHY_JSON_PATH", "CONFIG_IOT_JSON_PATH"):
        monkeypatch.setenv(variable, str(tmp_path / "missing.json"))
    monkeypatch.setenv("SIMULATOR_MOCK_AWS", "true")

    async def check_startup():
        async with user_simulation(main_file=root / "main.py") as user:
            response = await user.http_client.get("/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

            await user.open("/")
            user.find("Digital Twin Simulation: MGrid")
            user.find("Type: MGrid-WWBRxzKmtE9TFbUFMgFkBz")
            assert len(user.find("Start/Stop").elements) == 12

    asyncio.run(check_startup())
