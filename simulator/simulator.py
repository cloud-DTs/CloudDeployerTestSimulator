import json
import threading
import boto3
from flask import Flask, render_template, redirect, url_for, session, request, jsonify
import os
from model import Payloads
import time
import random
from datetime import datetime, timezone

app = Flask(__name__)
app.secret_key = "simulation_secret_key"
JSON_PATH = os.getenv('JSON_PATH', './test.json')
TWIN_NAME = os.getenv('TWIN_NAME', 'Twin')
TOPIC = os.getenv('TOPIC', 'Topic')

active_threads = {}
#client = boto3.client('iot-data', region_name='eu-central-1')


def safe_float(value, default=0.0):
    if value is None or str(value).strip() == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default

sim_settings = {"SIM_TIME": 10}
def generate_value(config, data_type):
    mode = config.get("mode")

    if "VECTOR" in data_type:
        if mode == "vector_custom":
            raw_vec = config.get("vector", "")
            return [float(x.strip()) if "DOUBLE" in data_type else int(float(x.strip()))
                    for x in raw_vec.split(",") if x.strip()]

        elif mode == "vector_uniform":
            raw_min = config.get("vec_min", "")
            raw_max = config.get("vec_max", "")
            min_vec = [float(x.strip()) if "DOUBLE" in data_type else int(float(x.strip()))
                       for x in raw_min.split(",") if x.strip()]
            max_vec = [float(x.strip()) if "DOUBLE" in data_type else int(float(x.strip()))
                       for x in raw_max.split(",") if x.strip()]

            result = []
            for mn, mx in zip(min_vec, max_vec):
                if "DOUBLE" in data_type:
                    result.append(round(random.uniform(mn, mx), 2))
                else:
                    result.append(random.randint(int(mn), int(mx)))
            return result

    if "INTEGER" in data_type or "DOUBLE" in data_type:
        if mode == "uniform":
            mn = safe_float(config.get("min"), 0.0)
            mx = safe_float(config.get("max"), 100.0)
            val = random.uniform(mn, mx)
            return round(val, 2) if "DOUBLE" in data_type else int(val)

        elif mode == "normal":
            mean = safe_float(config.get("mean"), 0.0)
            stddev = safe_float(config.get("stddev"), 1.0)
            val = random.gauss(mean, stddev)
            return round(val, 2) if "DOUBLE" in data_type else int(val)

    if "STRING" in data_type:
        if mode == "fixed_list":
            raw_list = config.get("list", "low,medium,high")
            words = [x.strip() for x in raw_list.split(",") if x.strip()]
            return random.choice(words) if words else "low"
        elif mode == "random_string":
            return random.choice(["status_ok", "status_warn", "status_error"])

    return 0

def simulation_loop(unique_key, real_device_id, config, data_name, data_type):
    print(f"Thread started for unique property: {unique_key}")
    mode = config.get("mode")

    current_value = None
    mn = mx = step = None
    if mode == "range":
        mn = safe_float(config.get("min"), 0.0)
        mx = safe_float(config.get("max"), 100.0)
        step = safe_float(config.get("step"), 1.0)
        current_value = mn

    while active_threads.get(unique_key, {}).get("run", False):
        if mode == "range":
            simulated_value = round(current_value, 2) if "DOUBLE" in data_type else int(current_value)
            current_value += step
            if current_value > mx:
                current_value = mn
        else:
            simulated_value = generate_value(config, data_type)

        now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        payload_dict = {
            "iotDeviceId": real_device_id,
            "time": now_utc,
            data_name: simulated_value
        }

        print(f"Publishing to {TOPIC}: {payload_dict}")
        live_sim_time = sim_settings.get("SIM_TIME", 10.0)
        print(f"Sleeping for {live_sim_time} seconds...")
        time.sleep(live_sim_time)

    print(f"Thread stopped for unique property: {unique_key}")


@app.route('/toggle-device', methods=['POST'])
def toggle_device():
    data = request.json
    unique_key = data.get("unique_key")
    should_run = data.get("run")

    if should_run:
        if unique_key in active_threads and active_threads[unique_key]["run"]:
            return jsonify({"status": "already running", "unique_key": unique_key})

        active_threads[unique_key] = {"run": True}

        device_meta = session.get("payloads", {}).get(unique_key, {})
        real_device_id = device_meta.get("id")
        data_name = device_meta.get("dataName", "value")
        data_type = device_meta.get("dataType", "INTEGER")

        thread = threading.Thread(
            target=simulation_loop,
            args=(unique_key, real_device_id, data, data_name, data_type),
        )
        thread.daemon = True
        thread.start()

        if "payloads" in session and unique_key in session["payloads"]:
            session["payloads"][unique_key]["run"] = True
            session.modified = True

        return jsonify({"status": "started", "unique_key": unique_key})
    else:
        if unique_key in active_threads:
            active_threads[unique_key]["run"] = False

        if "payloads" in session and unique_key in session["payloads"]:
            session["payloads"][unique_key]["run"] = False
            session.modified = True

        return jsonify({"status": "stopped", "unique_key": unique_key})


def createPayloads():
    if session.get("payloads", {}) != {}:
        return
    pl = Payloads()
    pl.read_from_json(JSON_PATH)
    session['payloads'] = {
        unique_key: {
            "id": p.id,
            "dataName": p.dataName,
            "dataType": str(p.dataType),
            "run": p.run
        }
        for unique_key, p in pl.payloadsDict.items()
    }


def update_session_with_thread_states():
    if "payloads" not in session:
        return
    for unique_key in session["payloads"].keys():
        is_alive = active_threads.get(unique_key, {}).get("run", False)
        session["payloads"][unique_key]["run"] = is_alive

    session.modified = True


@app.route('/')
def index():
    createPayloads()
    update_session_with_thread_states()
    if "SIM_TIME" not in session:
        session["SIM_TIME"] = sim_settings["SIM_TIME"]
    return render_template('index.html', TWIN_NAME=TWIN_NAME, TOPIC=TOPIC)

@app.route('/update-sim-time', methods=['POST'])
def update_sim_time():
    data = request.json
    sim_time = data.get("sim_time", 10)
    try:
        new_time = float(sim_time) if float(sim_time) > 0 else 2.0
        session["SIM_TIME"] = new_time
        sim_settings["SIM_TIME"] = new_time
    except (ValueError, TypeError):
        session["SIM_TIME"] = sim_settings["SIM_TIME"]

    session.modified = True
    return jsonify({"status": "success", "SIM_TIME": sim_settings["SIM_TIME"]})

if __name__ == '__main__':
    app.run(debug=True, port=5000)