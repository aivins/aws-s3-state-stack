from functools import cache

from cdktf_helpers.settings.aws.utils import boto3_session, tags

from . import types


@cache
def default_vpc():
    ec2 = boto3_session().client("ec2")
    response = ec2.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    vpc = response["Vpcs"][0] if response["Vpcs"] else None
    if not vpc:
        raise TypeError("No default VPC found")
    return types.Vpc(id=vpc["VpcId"])


@cache
def default_subnets():
    vpc = default_vpc().resource
    return types.AwsResources(
        [types.Subnet(id=subnet.id) for subnet in vpc.subnets.all()]
    )


def default_private_subnets():
    subnets = default_subnets()
    private_subnets = [
        s for s in subnets if "private" in tags(s).get("Name", "").lower()
    ]
    return types.AwsResources(private_subnets or subnets)


def default_public_subnets():
    subnets = default_subnets()
    public_subnets = [s for s in subnets if "public" in tags(s).get("Name", "").lower()]
    return types.AwsResources(public_subnets or subnets)
