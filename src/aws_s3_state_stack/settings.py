import os
from typing import Tuple, Type

from pydantic import BaseModel, Field
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


class SubnetsSetting(Setting):
    value: str = Field(default_factory=default_subnet_ids)


class PrivateSubnetsSetting(Setting):
    value: str = Field(default_factory=default_private_subnet_ids)


class PubliceSubnetsSetting(Setting):
    value: str = Field(default_factory=default_public_subnet_ids)


class UserInputSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(self, field, field_name):
        if field.exclude:
            return None, "", False
        value = input("  Enter field value: ")
        description = input("  Enter field description: ")
        return (
            field.annotation(value=value, description=description),
            field_name,
            True,
        )

    def __call__(self):
        settings = self.settings_sources_data["ParameterStoreSettingsSource"]
        for field_name, field in self.settings_cls.model_fields.items():
            if field_name in settings:
                continue
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
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
        settings = self.settings_sources_data["InitSettingsSource"]
        namespace = self.settings_sources_data["InitSettingsSource"]["namespace"]
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
        descriptions = {p["Name"]: p["Description"] for p in response["Parameters"]}
        response = ssm.get_parameters_by_path(Path=namespace, Recursive=True)
        params = response.get("Parameters", [])
        for param in params:
            description = descriptions[param["Name"]]
            key = param["Name"][len(namespace) + 1 :]
            value = param["Value"]
            if key in settings:
                continue
            if key in self.settings_cls.model_fields:
                field = self.settings_cls.model_fields[key]
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
    app: str = Field(exclude=True)
    environment: str = Field(exclude=True)
    namespace: str = Field(exclude=True)

    def __init__(self, app: str, environment: str, **kwargs):
        namespace = f"/{app}/{environment}"
        super().__init__(
            namespace=namespace,
            app=app,
            environment=environment,
            **kwargs,
        )

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
        sources = [init_settings, ParameterStoreSettingsSource(settings_cls)]
        if not os.environ.get("CI", False):
            sources.append(UserInputSettingsSource(settings_cls))
        return tuple(sources)

    def save(self):
        ssm = boto3_session().client("ssm")
        for key, setting in self.model_dump().items():
            full_key = f"{self.namespace}/{key}"
            ssm.put_parameter(
                Type="String",
                Name=full_key,
                Value=setting["value"],
                Description=setting["description"],
            )
