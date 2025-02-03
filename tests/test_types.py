import boto3
from moto import mock_aws

from cdktf_helpers.settings.aws import HostedZone, Subnet


def test_hosted_zone():
    with mock_aws():
        route53 = boto3.Session().client("route53")
        response = route53.create_hosted_zone(Name="blah.com", CallerReference="dummy")
        zone = HostedZone(id=response["HostedZone"]["Id"])
        assert zone.name == "blah.com."


def test_subnet():
    with mock_aws():
        ec2 = boto3.Session().resource("ec2")
        subnet = next(subnet for subnet in ec2.subnets.all())
        subnet_id = subnet.id
        cidr_block = subnet.cidr_block
        subnet = Subnet(id=subnet_id)
        assert subnet.id == subnet_id
        assert subnet.cidr_block == cidr_block
