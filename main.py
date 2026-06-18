import io
import json
import os
import tarfile
import tempfile

import pulumi_tls as tls
import pulumi
import pulumi_aws as aws

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


def get_string_for_user_data(bucket_name: pulumi.Input[str], s3_key: str) -> pulumi.Output[str]:
    region = aws.get_region().name
    return pulumi.Output.from_input(bucket_name).apply(lambda bucket: f"""#!/bin/bash
set -ex
exec > /home/ubuntu/bootstrap.log 2>&1

sudo apt-get update -y
sudo apt-get install python3-pip python3-flask unzip curl -y
sudo apt install python3.12-venv -y
mkdir -p /home/ubuntu/app

# Ubuntu's "awscli" apt package is unreliable across releases - install the
# official AWS CLI v2 directly instead.
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp
sudo /tmp/aws/install
which aws
aws --version

aws s3 cp s3://{bucket}/{s3_key} /tmp/app.tar.gz --region {region}
tar -xzf /tmp/app.tar.gz -C /home/ubuntu/app/
ls -la /home/ubuntu/app/

cd /home/ubuntu/app
sudo python3 -m venv .venv
sudo chown -R ubuntu:ubuntu /home/ubuntu/app/.venv
source /home/ubuntu/app/.venv/bin/activate
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

    app_bucket = aws.s3.BucketV2("simulator-app-bucket")

    aws.s3.BucketPublicAccessBlock(
        "simulator-app-bucket-pab",
        bucket=app_bucket.id,
        block_public_acls=True,
        block_public_policy=True,
        ignore_public_acls=True,
        restrict_public_buckets=True,
    )

    tar_path = package_directory_to_tar_file(IAC_PATH)
    app_object = aws.s3.BucketObjectv2(
        "simulator-app-object",
        bucket=app_bucket.id,
        key=S3_KEY,
        source=pulumi.FileAsset(tar_path),
        source_hash=pulumi.Output.from_input(_sha256_of_file(tar_path)),
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
        user_data=get_string_for_user_data(app_bucket.bucket, S3_KEY),
        monitoring=True,
        force_destroy=True,
        user_data_replace_on_change=True,
        opts=pulumi.ResourceOptions(depends_on=[app_object]),
    )

    pulumi.export("public_ip", ec2Instance.public_ip)
    pulumi.export("private_key_pem", pulumi.Output.secret(ssh_key.private_key_pem))
    pulumi.export("applicationURL", pulumi.Output.concat("http://", ec2Instance.public_ip, ":5000"))
    pulumi.export("app_bucket", app_bucket.bucket)


def _sha256_of_file(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


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


config = pulumi.Config()
iot_path = config.get("config_iot_json_path") or "./iot_device.json"
config_path = config.get("config_json_path") or "./config.json"
config_hierarchy = config.get("config_hierarchy_json_path") or "./hierarchy.json"

paste_config_file_in_sim(iot_path, config_path, config_hierarchy)
createVM()