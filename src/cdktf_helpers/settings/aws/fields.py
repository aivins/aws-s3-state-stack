from pydantic import Field

from .defaults import (
    default_private_subnets,
    default_public_subnets,
    default_subnets,
    default_vpc,
)


def VpcField(description="VPC ID", **kwargs):
    return Field(default_factory=default_vpc, description=description, **kwargs)


def SubnetsField(description="Subnet IDs", **kwargs):
    return Field(default_factory=default_subnets, description=description, **kwargs)


def PrivateSubnetsField(description="Subnet IDs", **kwargs):
    return Field(
        default_factory=default_private_subnets, description=description, **kwargs
    )


def PublicSubnetsField(description="Subnet IDs", **kwargs):
    return Field(
        default_factory=default_public_subnets, description=description, **kwargs
    )


def HostedZoneField(description="Hosted Zone", **kwargs):
    return Field(description=description, **kwargs)
