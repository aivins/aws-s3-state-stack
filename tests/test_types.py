import boto3
import pytest
from moto import mock_aws

from cdktf_helpers.settings.aws import (
    HostedZone,
    Subnet,
    Vpc,
)


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
