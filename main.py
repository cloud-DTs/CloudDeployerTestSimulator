import argparse, os
from dotenv import load_dotenv
load_dotenv()

parser = argparse.ArgumentParser()
parser.add_argument('--twin_dir', required=True, help='folder with the four config jsons of the twin')
args, _ = parser.parse_known_args()
os.environ['CONFIG_JSON_PATH'] = os.path.join(args.twin_dir, 'config.json')
os.environ['CONFIG_HIERARCHY_JSON_PATH'] = os.path.join(args.twin_dir, 'config_hierarchy.json')
os.environ['CONFIG_IOT_JSON_PATH'] = os.path.join(args.twin_dir, 'config_iot_devices.json')

from simulator.simulator import main
if __name__ in {"__main__", "__mp_main__"}:
    main()