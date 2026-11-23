# Digital Twin Simulator Manager

Generate device data for Cloud Deployer configurations. The interface shows each
component's device ID, full Component Type ID, and properties.

## Local setup

Use Python 3.12 or later. Run these commands from the repository root in PowerShell.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

python main.py --twin_dir ./input
```

Open http://localhost:5000. On Linux or macOS, activate the environment with
`source .venv/bin/activate`.

Use `--twin_dir` to select the directory for all three configuration files.
To select files individually, set `CONFIG_JSON_PATH`, `CONFIG_HIERARCHY_JSON_PATH`,
and `CONFIG_IOT_JSON_PATH` and run `python main.py`. An explicit `--twin_dir`
takes precedence over those variables. Each unset path defaults to the
corresponding file in the current working directory.

Mock mode is the default. Generated messages go to the process log. To publish to AWS, set
`SIMULATOR_MOCK_AWS=false` and supply AWS credentials with `iot:Publish` access to
the twin's topic. Set `AWS_REGION` to the deployment region. The simulator uses
one `boto3 iot-data` client and AWS credentials. It does not use device certificates.
This is HTTPS Publish to AWS IoT Core, not a device MQTT connection.
Environment credentials and an explicit AWS profile take precedence over a
legacy `CONFIG_CREDENTIALS_JSON` file. Temporary credentials use
`AWS_SESSION_TOKEN`; a legacy file can supply `aws_session_token`.

## Configuration and shared types

The simulator reads `config.json`, `config_iot_devices.json`, and
`config_hierarchy.json`. Device configuration can be a flat device list or an
entity tree with device properties on component nodes.
An entity without `name` is displayed using its `id`, as in the manager.
Supported types match the manager: `BOOLEAN`, `INTEGER`, `LONG`, `DOUBLE`,
`STRING`, `VECTOR_INTEGER`, `VECTOR_DOUBLE`, and `VECTOR_STRING`.

For twin `dt`, hierarchy references follow these rules:

| Component fields | Full Component Type ID | Device binding |
|---|---|---|
| `iotDeviceId: sensor-a` | `dt-sensor-a` | `sensor-a` |
| `iotDeviceId: sensor-a`, `componentTypeId: shared` | `dt-shared` | `sensor-a` |
| `componentTypeId: dt-shared` | `dt-shared` | The only configured device for this type |

With an explicit device ID, the type name is logical. The twin prefix is always
added, including when the logical name already starts with that prefix.
Without a device ID, the type ID is the full AWS ID and is used as supplied.
Hierarchy type names override type names in device configuration before bindings
are resolved across all root entities.

A type shared by several devices needs an explicit `iotDeviceId` on each
hierarchy component. Unknown device IDs, conflicting duplicate device
configurations, and incompatible shared schemas stop loading with an error.
Shared schemas must have the same property names and data types. Property order
and per-device `initValue` values can differ. Initial values do not select a
simulation mode or set the generator's start value.

A full type ID absent from the configured device types is an external reference.
The interface shows its status without simulation controls or AWS lookup.

All devices publish to `<digital_twin_name>/iot-data`. Each message contains
`iotDeviceId`, `time`, and the generated property. Shared types retain separate
device IDs and controls. Cloud Deployer manages one shared IoT policy per twin;
each device retains its own Thing and certificate. Debug ingestion timing fields
are added by the cloud pipeline.

Aliases of the same device share the same attribute controls and running state.
BOOLEAN supports fixed and random values. LONG and INTEGER uniform/range values
retain integer precision. VECTOR_STRING accepts comma-separated strings; numeric
vectors also support equal-length minimum/maximum bounds. Invalid values and
non-finite numbers stop the affected generator and appear as an error in the UI.
API integer values must be finite whole numbers; API doubles retain their source
precision. A forecast-only series has no current sample and is skipped.

The publish interval must be finite and at least 0.1 seconds. Stop wakes sleeping
workers immediately. A stopped or failed worker cannot keep its row marked as
running. Repeated starts cannot revive an earlier worker. Synthetic timestamps
are unique per device, including across independently generated properties.

API sample timestamps are preserved. The current manager persister replaces a
whole DynamoDB item for each `(iotDeviceId, time)` key. Do not run several API
properties on the same device at the same source timestamp: later writes can
replace earlier properties. Those source records require a single combined
device message or an atomic merge in the persister.

## Docker and examples

```powershell
docker compose up --build
```

Compose loads the MGrid example from `input/`. The Battery example is in
`input/battery/`. To run two devices that share a Component Type, use this command sequence.

```powershell
$env:SIMULATOR_INPUT_HOST_DIR = './input/shared-component-type'
docker compose up --build
```

To use the manager's configuration files, set `SIMULATOR_INPUT_HOST_DIR` to their
directory, for example `../digital-twin-manager`. Compose mounts the three files
as read-only files. The MGrid event configuration uses the example callback in
`lambda_functions/event_actions/high-temperature-callback` under the manager's repository root.

To run the locally built image directly from PowerShell, mount a configuration directory.

```powershell
docker run --rm -p 127.0.0.1:5000:5000 --mount "type=bind,source=$((Resolve-Path ./input).Path),target=/twin,readonly" cloud-deployer-test-simulator:local --twin_dir /twin
```

Docker checks `/health` on port 5000. On a push to `main` or a `v*` tag, the
GitHub Actions workflow publishes the image to `ghcr.io/<owner>/<repository>`.
Both parts of the package name use lowercase.

## Tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests use temporary configuration files and a local AWS substitute. They do not
publish to AWS.
