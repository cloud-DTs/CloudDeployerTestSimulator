import io
import json
import os
import tarfile
import tempfile
import uuid

import pulumi_tls as tls
import pulumi
import pulumi_aws as aws
import pulumi_std as std
import pulumi_local as local
from dotenv import load_dotenv
import pulumi_command as command
load_dotenv()

IAC_PATH = "./simulator"
VM_ROOT_PATH = "simulator"
S3_KEY = "simulator/app.tar.gz"


def package_directory_to_tar_file(src_dir: str) -> str:
    tmp_path = os.path.join(tempfile.gettempdir(), "simulator-app.tar.gz")
    with tarfile.open(tmp_path, mode="w:gz") as tar:
        for root, _, files in os.walk(src_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, src_dir)
                tar.add(full_path, arcname=rel_path)
    return tmp_path


def get_string_for_user_data(bucket_name, s3_key, app_hash):
    region = aws.get_region().region
    return pulumi.Output.all(bucket_name, app_hash).apply(lambda args: f"""#!/bin/bash
# Config-Trigger-Hash: {args[1]}
set -ex
exec > /home/ubuntu/bootstrap.log 2>&1

sudo apt-get update -y
sudo apt-get install -y python3-pip python3.12-venv

mkdir -p /home/ubuntu/app
cd /home/ubuntu/app
sudo python3 -m venv .venv
sudo chown -R ubuntu:ubuntu /home/ubuntu/app/.venv
source .venv/bin/activate

pip install boto3
python3 -c "
import boto3
boto3.client('s3', region_name='{region}').download_file('{args[0]}', '{s3_key}', '/tmp/app.tar.gz')
"
tar -xzf /tmp/app.tar.gz -C /home/ubuntu/app/
ls -la /home/ubuntu/app/

pip install -r requirements.txt

nohup python3 simulator.py > /home/ubuntu/flask.log 2>&1 &
""")


def createVM():
    sec_group = aws.ec2.SecurityGroup(
        "web-secgroup",
        description="Enable SSH and Flask access",
        ingress=[
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=22,
                to_port=22,
                cidr_blocks=["0.0.0.0/0"],
            ),
            aws.ec2.SecurityGroupIngressArgs(
                protocol="tcp",
                from_port=5000,
                to_port=5000,
                cidr_blocks=["0.0.0.0/0"],
            )
        ],
        egress=[
            aws.ec2.SecurityGroupEgressArgs(
                protocol="-1",
                from_port=0,
                to_port=0,
                cidr_blocks=["0.0.0.0/0"],
            )
        ]
    )

    app_bucket = aws.s3.Bucket("simulator-app-bucket")

    aws.s3.BucketPublicAccessBlock(
        "simulator-app-bucket-pab",
        bucket=app_bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True,
    )

    tar_path = package_directory_to_tar_file(IAC_PATH)

    pulumi_app_hash = std.filesha256(input=tar_path).result

    app_object = aws.s3.BucketObject(
        "simulator-app-object",
        bucket=app_bucket.id,
        key=S3_KEY,
        source=pulumi.FileAsset(tar_path),
        source_hash=pulumi_app_hash,
    )

    iot_role = aws.iam.Role(
        "simulator-iot-role",
        assume_role_policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
            }]
        })
    )

    aws.iam.RolePolicy(
        "iot-publish-policy",
        role=iot_role.id,
        policy=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "iot:Publish",
                "Resource": "*"
            }]
        })
    )

    aws.iam.RolePolicy(
        "s3-app-read-policy",
        role=iot_role.id,
        policy=app_bucket.arn.apply(lambda arn: json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "Resource": f"{arn}/{S3_KEY}"
            }]
        }))
    )

    ssh_key = tls.PrivateKey(
        "simulator-ssh-key",
        algorithm="RSA",
        rsa_bits=4096,
    )
    key_pair = aws.ec2.KeyPair(
        "simulator-key",
        public_key=ssh_key.public_key_openssh
    )

    instance_profile = aws.iam.InstanceProfile("simulator-profile", role=iot_role.name)

    ec2Instance = aws.ec2.Instance(
        "simulator-vm",
        ami="ami-01e444924a2233b07",
        vpc_security_group_ids=[sec_group.id],
        instance_type="t3.micro",
        iam_instance_profile=instance_profile.name,
        key_name=key_pair.key_name,
        user_data=get_string_for_user_data(app_bucket.bucket, S3_KEY, pulumi_app_hash),
        monitoring=True,
        force_destroy=True,
        user_data_replace_on_change=True,
        opts=pulumi.ResourceOptions(depends_on=[app_object]),
    )

    wait_for_app = command.local.Command(
        "wait-for-app",
        create=ec2Instance.public_ip.apply(lambda ip: f"""
    for i in $(seq 1 60); do
      if curl -sf -o /dev/null "http://{ip}:5000"; then
        echo "STARTED"
        exit 0
      fi
      echo "Starting simulator... ($i/60)"
      sleep 5
    done
    echo "Simulator not reachable ERROR" >&2
    exit 1
    """),
        triggers=[pulumi_app_hash],
        opts=pulumi.ResourceOptions(depends_on=[ec2Instance]),
    )


    pulumi.export("public_ip", ec2Instance.public_ip)
    pulumi.export("applicationURL", ec2Instance.public_ip.apply(lambda ip: f"http://{ip}:5000"))
    pulumi.export("app_bucket", app_bucket.bucket)
    pulumi.export("ssh_private_key", pulumi.Output.secret(ssh_key.private_key_pem))


def paste_config_file_in_sim(path_iot, path_config, path_config_hier):
    for src_path, target_name in [
        (path_iot, "config_iot_devices"),
        (path_config_hier, "config_hierarchy"),
        (path_config, "config"),
    ]:
        with open(src_path, 'r') as f:
            fl = json.load(f)

        with open(os.path.join(IAC_PATH, f"{target_name}.json"), 'w') as fw:
            json.dump(fl, fw, indent=4)


iot_path = os.getenv("CONFIG_IOT_JSON_PATH")
config_path = os.getenv("CONFIG_JSON_PATH")
config_hierarchy = os.getenv("CONFIG_HIERARCHY_JSON_PATH")
config_credentials_path = os.getenv("CONFIG_CREDENTIALS_JSON")


with open(config_credentials_path, 'r') as f:
    config_credentials = json.load(f)

if config_credentials:
    os.environ["AWS_ACCESS_KEY_ID"] = config_credentials.get("aws_access_key_id", "")
    os.environ["AWS_SECRET_ACCESS_KEY"] = config_credentials.get("aws_secret_access_key", "")
    os.environ["AWS_DEFAULT_REGION"] = config_credentials.get("aws_region", "")

paste_config_file_in_sim(iot_path, config_path, config_hierarchy)
createVM()