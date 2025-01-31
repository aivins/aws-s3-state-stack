import os
import re
from typing import List, Tuple, Type, get_origin

from pydantic import BaseModel, Field, computed_field
from pydantic_core import PydanticUndefined
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from .aws import (
    boto3_session,
    default_private_subnet_ids,
    default_public_subnet_ids,
    default_subnet_ids,
    default_vpc_id,
)


class Setting(BaseModel):
    value: str
    description: str = ""


class VpcSetting(Setting):
    value: str = Field(default_factory=default_vpc_id)
    description: str = "VPC ID"


class SubnetsSetting(Setting):
    value: List[str] = Field(default_factory=default_subnet_ids)
    description: str = "Subnet IDs"


class PrivateSubnetsSetting(Setting):
    value: List[str] = Field(default_factory=default_private_subnet_ids)
    description: str = "Private Subnet IDs"


class PubliceSubnetsSetting(Setting):
    value: List[str] = Field(default_factory=default_public_subnet_ids)
    description: str = "Public Subnet IDs"


class UserInputSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(self, field, field_name, setting):
        default_value = setting.value
        description = None

        if field.default is not PydanticUndefined:
            default_value = default_value or field.default.value
            description = field.default.description

        if description is None:
            description_field = field.annotation.model_fields["description"]
            if description_field.default:
                description = description_field.default

        value = None
        while not value:
            default_msg = f" [{default_value}]" if default_value is not None else ""
            field_id = f"{description} ({field_name})" if description else field_name
            value = input(f"{field_id}{default_msg}: ")
            if not value and default_value:
                value = default_value
        return (
            field.annotation(value=value, description=description or ""),
            field_name,
            True,
        )

    def __call__(self):
        source = self.settings_sources_data["ParameterStoreSettingsSource"]
        settings = {}
        for field_name, field in self.settings_cls.model_fields.items():
            if field.exclude:
                continue
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name, source[field_name]
            )
            if field_key:
                settings[field_key] = field_value
        return settings


class ParameterStoreSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._settings = None

    def fetch_settings(self):
        ssm = boto3_session().client("ssm")
        source = self.settings_sources_data["InitSettingsSource"]
        namespace = self.settings_cls.format_namespace(
            source["app"], source["environment"]
        )
        response = ssm.describe_parameters(
            ParameterFilters=[
                {
                    "Key": "Name",
                    "Option": "BeginsWith",
                    "Values": [
                        namespace,
                    ],
                },
            ]
        )
        descriptions = {
            p["Name"]: p.get("Description", "") for p in response["Parameters"]
        }
        response = ssm.get_parameters_by_path(Path=namespace, Recursive=True)
        params = response.get("Parameters", [])
        settings = {}
        for param in params:
            description = descriptions[param["Name"]]
            key = param["Name"][len(namespace) + 1 :]
            value = param["Value"]
            if key in source:
                continue
            if key in self.settings_cls.model_fields:
                field = self.settings_cls.model_fields[key]
                if (
                    get_origin(field.annotation.model_fields["value"].annotation)
                    is list
                ):
                    value = [v.replace("\\", "") for v in re.split(r"(?<!\\),", value)]
                settings[key] = field.annotation(value=value, description=description)
        return settings

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


class AppSettings(BaseSettings):
    model_config = {"extra": "allow"}
    app: str = Field(exclude=True, default="app")
    environment: str = Field(exclude=True, default="dev")

    @computed_field
    def namespace(self) -> str:
        return self.format_namespace(self.app, self.environment)

    @classmethod
    def format_namespace(cls, app: str, environment: str) -> str:
        return f"/{app}/{environment}"

    def set(self, key, value, description=""):
        key = key.strip()
        if not key:
            raise Exception("Cannot set an empty key")
        if key not in self.model_fields:
            raise Exception(f"{key} is not a field on {self.__class__.__name__}")
        field = self.model_fields[key]
        setattr(self, key, field.annotation(value=value, description=description))

    def save(self):
        pass


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
        fields = [k for k, f in self.model_fields.items() if not f.exclude]
        for key in fields:
            setting = getattr(self, key)
            full_key = f"{self.namespace}/{key}"
            if isinstance(setting.value, list):
                value = ",".join([v.replace(",", "\,") for v in setting.value])
            else:
                value = setting.value
            ssm.put_parameter(
                Type="String",
                Name=full_key,
                Value=value,
                Description=setting.description,
                Overwrite=True,
            )
