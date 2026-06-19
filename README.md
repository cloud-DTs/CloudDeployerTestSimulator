# Digital Twin Simulator Manager

An Infrastructure-as-Code (IaC) deployment utility using Pulumi to spin up an EC2-hosted digital twin simulation runner. The engine runs a local Flask configuration interface and concurrency-managed simulation threads that stream mock physical data payloads with MQTT.

## # Prerequisites

### Install System Dependencies
Ensure you have the required CLI tools installed and available in your shell's execution path.
You need pulumi https://www.pulumi.com/docs/install/

# Venv
Create a python venv and install the requirements.txt
# First Time
```bash
pulumi login --local
pulumi package add terraform-provider hashicorp/local
pulumi stack init dev
export PULUMI_CONFIG_PASSPHRASE=""

```
Enter the input paths in the .env file and paste the config files in the ./input folder
# Deploy
```bash
pulumi up
```
Output:
  ~ applicationURL : "" <-- this you can open in a browser


# Connecting to VM directly
```bash
ssh -i <(pulumi stack output ssh_private_key --show-secrets) ubuntu@$(pulumi stack output public_ip)
```