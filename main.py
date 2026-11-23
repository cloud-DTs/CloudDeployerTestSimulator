import argparse
import os
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description="Run the digital twin simulator.")
    parser.add_argument("--twin_dir", type=Path, help="Directory containing the simulator configuration files")
    args, _ = parser.parse_known_args()

    load_dotenv()
    if args.twin_dir is not None:
        os.environ["CONFIG_JSON_PATH"] = str(args.twin_dir / "config.json")
        os.environ["CONFIG_HIERARCHY_JSON_PATH"] = str(args.twin_dir / "config_hierarchy.json")
        os.environ["CONFIG_IOT_JSON_PATH"] = str(args.twin_dir / "config_iot_devices.json")

    from simulator.simulator import main as run_simulator

    run_simulator()


if __name__ in {"__main__", "__mp_main__"}:
    main()
