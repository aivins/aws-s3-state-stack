import json
from functools import cache
from typing import List, Tuple, Type

import boto3
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from .base import AppSettings


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


@cache
def default_private_subnets():
    subnets = default_subnets()
    private_subnets = [
        s for s in subnets if "private" in tags(s).get("Name", "").lower()
    ]
    return private_subnets or subnets


@cache
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


class ParameterStoreSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._settings = None

    def fetch_settings(self):
        from .utils import get_all_settings

        source = self.settings_sources_data["InitSettingsSource"]
        return {
            k: v
            for k, v in get_all_settings(
                self.settings_cls, source["app"], source["environment"]
            ).items()
            if k not in source
        }

    def get_field_value(self, field, field_name):
        if not self._settings:
            self._settings = self.fetch_settings()
        if field.exclude or field_name not in self._settings:
            return None, "", False

        return (
            self._settings[field_name],
            field_name,
            True,
        )

    def __call__(self):
        settings = {}
        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
            )
            if field_key:
                settings[field_key] = field_value
        return settings


class AwsAppSettings(AppSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        *args,
        **kwargs,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, ParameterStoreSettingsSource(settings_cls))

    def save(self):
        ssm = boto3_session().client("ssm")
        saved = []
        for key, field in self.model_fields.items():
            if field.exclude:
                continue
            value = getattr(self, key)
            full_key = f"{self.namespace}/{key}"
            ssm.put_parameter(
                Type="String",
                Name=full_key,
                Value=json.dumps(value),
                Description=field.description or "",
                Overwrite=True,
            )
            saved.append(key)
        return saved
