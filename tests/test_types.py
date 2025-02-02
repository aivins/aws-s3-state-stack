import boto3
from moto import mock_aws

from cdktf_helpers.settings.aws import HostedZone


def test_hosted_zone():
    with mock_aws():
        route53 = boto3.Session().client("route53")
        response = route53.create_hosted_zone(Name="blah.com", CallerReference="dummy")
        zone = HostedZone(id=response["HostedZone"]["Id"])
        assert zone.name == "blah.com."
