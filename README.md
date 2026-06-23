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
export PULUMI_CONFIG_PASSPHRASE=""
pulumi stack init dev


```
Enter the input paths in the .env file and paste the config files in the ./input folder
# Deploy
```bash
pulumi up
```
Output:
  ~ applicationURL : "" <--  open in a browser

# Destroy
```bash
pulumi destroy
```

# Connecting to VM directly
### For macOS & Linux
```bash
pulumi stack output ssh_private_key --show-secrets > temp_key.pem && chmod 400 temp_key.pem && ssh -i temp_key.pem ubuntu@$(pulumi stack output public_ip); rm -f temp_key.pem
```
On WSL
```bash
pulumi stack output ssh_private_key --show-secrets > /tmp/temp_key.pem && chmod 400 /tmp/temp_key.pem && ssh -i /tmp/temp_key.pem ubuntu@$(pulumi stack output public_ip); rm -f /tmp/temp_key.pem
````

### For Windows (PowerShell)
```powershell
pulumi stack output ssh_private_key --show-secrets | Set-Content -Path temp_key.pem; ssh -i temp_key.pem ubuntu@\$(pulumi stack output public_ip); Remove-Item -Force temp_key.pem
```
