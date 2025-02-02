from functools import cache

import boto3


def tags(resource):
    return {t["Key"]: t["Value"] for t in resource.tags}


@cache
def boto3_session():
    return boto3.Session()


@cache
def default_vpc():
    ec2 = boto3_session().resource("ec2")
    return next((vpc for vpc in ec2.vpcs.all() if vpc.is_default), None)


@cache
def default_subnets():
    vpc = default_vpc()
    return list(vpc.subnets.all())


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


def get_ids(resources):
    return [r.id for r in resources]


def default_vpc_id():
    return default_vpc().id


def default_subnet_ids():
    return get_ids(default_subnets())


def default_private_subnet_ids():
    return get_ids(default_private_subnets())


def default_public_subnet_ids():
    return get_ids(default_public_subnets())
