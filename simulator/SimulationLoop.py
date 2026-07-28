import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
import boto3

from .domain import Attribute, DataType 

CREDENTIALS_PATH = os.path.abspath(os.getenv('CONFIG_CREDENTIALS_JSON', './input/config_credentials.json'))

def safe_float(value, default=0.0):
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def safe_int(value, default=0):
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def parse_headers(raw_headers: str) -> dict:
    if raw_headers is None:
        return {}

    value = str(raw_headers).strip()
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def extract_json_value(payload, json_path: str):
    if json_path is None or str(json_path).strip() == "":
        return payload

    tokens = re.findall(r'[^.\[\]]+|\[\d+\]', str(json_path).strip())
    current = payload

    for token in tokens:
        if not token:
            continue

        if token.startswith('[') and token.endswith(']'):
            if not isinstance(current, list):
                return None
            index = int(token[1:-1])
            if index < 0 or index >= len(current):
                return None
            current = current[index]
        else:
            if isinstance(current, dict):
                current = current.get(token)
            else:
                return None

        if current is None:
            return None

    return current


def coerce_value(value, dtype: str):
    if dtype == "STRING":
        return str(value)

    if dtype == "INTEGER":
        if isinstance(value, bool):
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            try:
                return int(float(value))
            except ValueError:
                return 0
        return 0

    if dtype == "DOUBLE":
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        if isinstance(value, str):
            try:
                return round(float(value), 2)
            except ValueError:
                return 0.0
        return 0.0

    if dtype.startswith("VECTOR_"):
        if isinstance(value, list):
            base_dtype = dtype.replace("VECTOR_", "")
            return [coerce_value(item, base_dtype) for item in value]
        return []

    return value


DEFAULT_API_PROVIDER = {
    "name": "Energy Charts renewable share forecast",
    "url": "https://api.energy-charts.info/ren_share_forecast?country=de",
    "json_path": "ren_share",
}


def fetch_predefined_api_value(dtype: str):
    provider = DEFAULT_API_PROVIDER
    timeout = 15
    request = urllib.request.Request(provider["url"])

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_body = response.read().decode('utf-8')
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
        raise RuntimeError(f"API request failed: {exc}") from exc

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise ValueError("API response is not valid JSON") from exc

    extracted = extract_json_value(payload, provider["json_path"])
    if not isinstance(extracted, list) or not extracted:
        raise ValueError("API response did not contain a renewable-share list")

    latest_value = extracted[-1]
    return coerce_value(latest_value, dtype)


def fetch_api_value(config: dict, dtype: str):
    if config.get("api_url"):
        api_url = str(config.get("api_url", "")).strip()
        json_path = config.get("json_path", "")
        timeout = max(1, safe_int(config.get("timeout"), 10))
        headers = parse_headers(config.get("headers", ""))

        request = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw_body = response.read().decode('utf-8')
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError) as exc:
            raise RuntimeError(f"API request failed: {exc}") from exc

        try:
            payload = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise ValueError("API response is not valid JSON") from exc

        extracted = extract_json_value(payload, json_path)
        if extracted is None:
            raise ValueError("API response field was not found")

        return coerce_value(extracted, dtype)

    return fetch_predefined_api_value(dtype)


def generate_value(config: dict, dtype: str):
    mode = config.get("mode")

    if "VECTOR" in dtype:
        if mode == "vector_custom":
            raw_vec = config.get("vector", "")
            return [float(x.strip()) if "DOUBLE" in dtype else int(float(x.strip()))
                    for x in raw_vec.split(",") if x.strip()]
        elif mode == "vector_uniform":
            raw_min = config.get("vec_min", "")
            raw_max = config.get("vec_max", "")
            min_vec = [float(x.strip()) if "DOUBLE" in dtype else int(float(x.strip()))
                       for x in raw_min.split(",") if x.strip()]
            max_vec = [float(x.strip()) if "DOUBLE" in dtype else int(float(x.strip()))
                       for x in raw_max.split(",") if x.strip()]
            result = []
            for mn, mx in zip(min_vec, max_vec):
                if "DOUBLE" in dtype:
                    result.append(round(random.uniform(mn, mx), 2))
                else:
                    result.append(random.randint(int(mn), int(mx)))
            return result

    if dtype in ("INTEGER", "DOUBLE"):
        if mode == "uniform":
            mn = safe_float(config.get("min"), 0.0)
            mx = safe_float(config.get("max"), 100.0)
            val = random.uniform(mn, mx)
            return round(val, 2) if dtype == "DOUBLE" else int(val)
        elif mode == "normal":
            mean = safe_float(config.get("mean"), 0.0)
            stddev = safe_float(config.get("stddev"), 1.0)
            val = random.gauss(mean, stddev)
            return round(val, 2) if dtype == "DOUBLE" else int(val)

    if dtype == "STRING":
        if mode == "fixed_list":
            raw_list = config.get("list", "low,medium,high")
            words = [x.strip() for x in raw_list.split(",") if x.strip()]
            return random.choice(words) if words else "low"
        elif mode == "random_string":
            return random.choice(["status_ok", "status_warn", "status_error"])

    return 0

class AWS_CREDENTIALS:
    def __init__(self, credentials_path=CREDENTIALS_PATH):
        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Credentials file not found: {credentials_path}")
        with open(credentials_path, 'r') as f:
            self.credentials = json.load(f)

class SimulationLoop:
    def __init__(self, topic: str):
        self.topic = topic
        creds = AWS_CREDENTIALS().credentials
        self.client = boto3.client(
            'iot-data',
            region_name=creds["aws_region"],
            aws_access_key_id=creds["aws_access_key_id"],
            aws_secret_access_key=creds["aws_secret_access_key"],
        )
        self.active_runs: dict[str, dict] = {}
        self.sim_time = 10.0

    def is_running(self, attribute_id: str) -> bool:
        return self.active_runs.get(attribute_id, {}).get("run", False)

    def start_one(self, attribute: Attribute, real_device_id: str, config: dict):
        if self.is_running(attribute.id):
            return

        self.active_runs[attribute.id] = {"run": True}
        attribute.run = True

        thread = threading.Thread(
            target=self._loop,
            args=(attribute, real_device_id, config),
            daemon=True,
        )
        thread.start()

    def stop_one(self, attribute: Attribute):
        if attribute.id in self.active_runs:
            self.active_runs[attribute.id]["run"] = False
        attribute.run = False

    def _loop(self, attribute: Attribute, real_device_id: str, config: dict):
        mode = config.get("mode")
        dtype = attribute.dataType.value

        current_value = None
        mn = mx = step = None
        if mode == "range":
            mn = safe_float(config.get("min"), 0.0)
            mx = safe_float(config.get("max"), 100.0)
            step = safe_float(config.get("step"), 1.0)
            current_value = mn
        elif mode == "cycle":
            current_value = safe_int(config.get("start"), 0) % 24

        while self.active_runs.get(attribute.id, {}).get("run", False):
            if mode == "range":
                simulated_value = round(current_value, 2) if dtype == "DOUBLE" else int(current_value)
                current_value += step
                if current_value > mx:
                    current_value = mn
            elif mode == "cycle":
                simulated_value = round(float(current_value), 2) if dtype == "DOUBLE" else int(current_value)
                current_value = (current_value + 1) % 24
            elif mode == "api":
                try:
                    simulated_value = fetch_api_value(config, dtype)
                except Exception as exc:
                    print(f"API mode failed for {attribute.name}: {exc}")
                    time.sleep(self.sim_time)
                    continue
            else:
                simulated_value = generate_value(config, dtype)

            now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
            payload_dict = {
                "iotDeviceId": real_device_id,
                "time": now_utc,
                attribute.name: simulated_value,
            }

            print(f"Publishing to {self.topic}: {payload_dict}")
            try:

                response = self.client.publish(
                   topic=self.topic,
                   qos=1,
                   payload=json.dumps(payload_dict).encode('utf-8'),
                )
                print(f"AWS Response: {response.get('ResponseMetadata', {}).get('HTTPStatusCode')}")
            except Exception as e:
                print(f"Failed to publish to AWS IoT Core: {e}")

            time.sleep(self.sim_time)

        print(f"Thread stopped for: {attribute.name} ({attribute.id})")