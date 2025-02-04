import boto3
from moto import mock_aws

from cdktf_helpers.settings.aws import (
    AwsResources,
    HostedZone,
    Subnet,
    Vpc,
)


def test_collection():
    with mock_aws():
        subnet1 = Subnet(id="subnet-123")
        subnet2 = Subnet(id="subnet-456")
        subnet3 = Subnet(id="subnet-789")
        subnets: AwsResources[Subnet] = AwsResources([subnet1, subnet2])


def test_type_equality():
    with mock_aws():
        assert Vpc(id="vpc-12345") == Vpc(id="vpc-12345")
        assert Vpc(id="vpc-12345") != Vpc(id="vpc-67890")


def test_contains():
    with mock_aws():
        subnet1 = Subnet(id="subnet-123")
        subnet2 = Subnet(id="subnet-456")
        subnet3 = Subnet(id="subnet-789")
        subnets: AwsResources[Subnet] = AwsResources([subnet1, subnet2])
        assert subnet1 in subnets
        assert subnet2 in subnets
        assert subnet3 not in subnets
        assert subnet1.id in subnets
        assert subnet2.id in subnets
        assert subnet3.id not in subnets


def test_vpc():
    with mock_aws():
        vpc_id = list(boto3.Session().resource("ec2").vpcs.all())[0].id
        vpc = Vpc(id=vpc_id)
        assert vpc.resource.cidr_block


def test_subnet():
    with mock_aws():
        subnet = list(boto3.Session().resource("ec2").subnets.all())[0]
        subnet_id = subnet.id
        cidr_block = subnet.cidr_block
        subnet = Subnet(id=subnet_id)
        assert subnet.id == subnet_id
        assert subnet.cidr_block == cidr_block


def test_hosted_zone():
    with mock_aws():
        route53 = boto3.Session().client("route53")
        response = route53.create_hosted_zone(Name="blah.com", CallerReference="dummy")
        zone = HostedZone(id=response["HostedZone"]["Id"])
        assert zone.name == "blah.com."
