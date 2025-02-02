from functools import cached_property
from typing import Annotated

from pydantic import BaseModel, StringConstraints, computed_field

from .defaults import boto3_session

VpcId = Annotated[str, StringConstraints(pattern=r"^vpc-[a-z0-9]+$")]
SubnetId = Annotated[str, StringConstraints(pattern=r"^subnet-[a-z0-9]+$")]
HostedZoneId = Annotated[str, StringConstraints(pattern=r"^/hostedzone/[A-Z0-9]+$")]


class HostedZone(BaseModel):
    id: HostedZoneId

    @computed_field
    def name(self) -> str:
        return self.resource["Name"]

    @cached_property
    def resource(self):
        route53 = boto3_session().client("route53")
        response = route53.get_hosted_zone(Id=self.id)
        return response["HostedZone"]
