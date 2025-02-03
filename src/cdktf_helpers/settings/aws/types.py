from abc import ABC, abstractmethod
from functools import cached_property
from typing import Annotated

from pydantic import BaseModel, StringConstraints, computed_field

from .utils import boto3_session

VpcId = Annotated[str, StringConstraints(pattern=r"^vpc-[a-z0-9]+$")]
SubnetId = Annotated[str, StringConstraints(pattern=r"^subnet-[a-z0-9]+$")]
HostedZoneId = Annotated[str, StringConstraints(pattern=r"^/hostedzone/[A-Z0-9]+$")]


class AwsResource(BaseModel, ABC):
    @property
    @abstractmethod
    def resource(self):
        pass

    def __str__(self):
        return self.id


class Vpc(AwsResource):
    id: VpcId

    @cached_property
    def resource(self):
        resource = boto3_session().resource("ec2").Vpc(self.id)
        resource.load()
        return resource


class Subnet(AwsResource):
    id: SubnetId

    @cached_property
    def resource(self):
        resource = boto3_session().resource("ec2").Subnet(self.id)
        resource.load()
        return resource

    @computed_field
    def cidr_block(self) -> str:
        return self.resource.cidr_block


class HostedZone(AwsResource):
    id: HostedZoneId

    @cached_property
    def resource(self):
        route53 = boto3_session().client("route53")
        response = route53.get_hosted_zone(Id=self.id)
        return response["HostedZone"]

    @computed_field
    def name(self) -> str:
        return self.resource["Name"]
