# Digital Twin Simulator Manager

An Infrastructure-as-Code (IaC) deployment utility using Pulumi to spin up an EC2-hosted digital twin simulation runner. The engine runs a local Flask configuration interface and concurrency-managed simulation threads that stream mock physical data payloads with MQTT.

## # Prerequisites

### Install System Dependencies
Ensure you have the required CLI tools installed and available in your shell's execution path.
You need pulumi https://www.pulumi.com/docs/install/ and a aws-cli.

# Venv
Create a python venv and install the requirements.txt

# Deploy
```bash
pulumi config set config_iot_json_path "/home/marcocotrotzo/PycharmProjects/digital-twin-manager/config_iot_devices.json"
pulumi config set config_json_path "/home/marcocotrotzo/PycharmProjects/digital-twin-manager/config.json"
pulumi config set config_hierarchy_json_path "/home/marcocotrotzo/PycharmProjects/digital-twin-manager/config_hierarchy.json"
pulumi config set aws:region "eu-central-1"
pulumi up
```
Output:
  ~ applicationURL : "" <-- this you can open in a browser


# Connecting to VM directly
## Linux 
```bash
pulumi stack output private_key_pem --show-secrets > simulator-key.pem
chmod 400 simulator-key.pem
ssh -i simulator-key.pem ubuntu@$(pulumi stack output public_ip)
```
## Windows
```bash
pulumi stack output private_key_pem --show-secrets > simulator-key.pem
icacls simulator-key.pem /inheritance:r
icacls simulator-key.pem /grant:r "$($env:USERNAME):(R)"
ssh -i simulator-key.pem ubuntu@$(pulumi stack output public_ip)
```