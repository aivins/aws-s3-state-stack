from functools import cache

from cdktf_helpers.settings.aws.utils import boto3_session, tags

from . import types


@cache
def default_vpc():
    ec2 = boto3_session().resource("ec2")
    vpc = next((vpc for vpc in ec2.vpcs.all() if vpc.is_default), None)
    if not vpc:
        raise TypeError("No default VPC found")
    return types.Vpc(id=vpc.id)


@cache
def default_subnets():
    vpc = default_vpc().resource
    return [types.Subnet(id=subnet.id) for subnet in vpc.subnets.all()]


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
