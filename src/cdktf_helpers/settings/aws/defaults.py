from functools import cache

from cdktf_helpers.settings.aws.utils import boto3_session, tags

from . import types


@cache
def default_vpc():
    session = boto3_session()
    ec2 = session.client("ec2")
    response = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    vpc = response["Vpcs"][0] if response["Vpcs"] else None
    if not vpc:
        raise TypeError("No default VPC found")
    return session.resource("ec2").Vpc(vpc["VpcId"])


@cache
def default_subnets():
    return list(default_vpc().subnets.all())


def default_private_subnets():
    subnets = default_subnets()
    private_subnets = [
        s for s in subnets if "private" in tags(s).get("Name", "").lower()
    ]
    return private_subnets or subnets


def default_public_subnets():
    subnets = default_subnets()
    public_subnets = [s for s in subnets if "public" in tags(s).get("Name", "").lower()]
    return public_subnets or subnets


def default_vpc_id():
    return default_vpc().id


def default_subnet_ids():
    return [subnet.id for subnet in default_subnets()]


def default_private_subnet_ids():
    return [s.id for s in default_private_subnets()]


def default_public_subnet_ids():
    return [s.id for s in default_public_subnets()]
