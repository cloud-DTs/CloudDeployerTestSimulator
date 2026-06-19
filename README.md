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
pulumi package add terraform-provider hashicorp/local
pulumi stack init dev
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
ssh -i simulator-key.pem ubuntu@$(pulumi stack output public_ip)
```