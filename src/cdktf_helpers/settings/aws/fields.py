from pydantic import Field

from .defaults import (
    default_private_subnet_ids,
    default_public_subnet_ids,
    default_subnet_ids,
    default_vpc_id,
)


def VpcField(description="VPC ID", **kwargs):
    return Field(default_factory=default_vpc_id, description=description, **kwargs)


def SubnetsField(description="Subnet IDs", **kwargs):
    return Field(default_factory=default_subnet_ids, description=description, **kwargs)


def PrivateSubnetsField(description="Subnet IDs", **kwargs):
    return Field(
        default_factory=default_private_subnet_ids, description=description, **kwargs
    )


def PublicSubnetsField(description="Subnet IDs", **kwargs):
    return Field(
        default_factory=default_public_subnet_ids, description=description, **kwargs
    )


def HostedZoneField(description="Hosted Zone", **kwargs):
    return Field(description=description, **kwargs)
