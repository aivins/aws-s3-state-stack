from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Type, TypedDict

import boto3
import botocore.client
from pydantic import BaseModel, PrivateAttr, computed_field
from pydantic_settings import (
    BaseSettings,
    InitSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# @dataclass
# class Setting:
#     namespace: str
#     key: str
#     value: str
#     description: str = ""
#     required: bool = False

#     def __str__(self) -> str:
#         return self.value


class Setting(BaseModel):
    key: str
    value: str
    description: str = ""


class ParameterStoreSettingsSource(PydanticBaseSettingsSource):
    def get_field_value(self, field, field_name):
        breakpoint()

    def __call__(self):
        session = self.settings_sources_data["InitSettingsSource"]["_session"]
        ssm = session.client("ssm")
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
        settings = {}
        for param in params:
            description = descriptions[param["Name"]]
            key = param["Name"][len(namespace) + 1 :]
            if key in self.settings_cls.model_fields:
                settings[key] = Setting(
                    key=key, value=param["Value"], description=description
                )
        return settings


class AppSettings(BaseSettings):
    model_config = {
        "extra": "allow",
    }
    app: str
    environment: str
    namespace: str

    def __init__(self, app: str, environment: str, **kwargs):
        namespace = f"/{app}/{environment}"
        super().__init__(
            namespace=namespace,
            app=app,
            environment=environment,
            **kwargs,
        )
        # self._namespace = namespace

    # def _get(self, key: str) -> Setting:
    #     return getattr(self, key)

    # def _set(self, key: str, **data):
    #     return setattr(self, key, data)

    # def get(self, key: str) -> Setting:
    #     return self._get(key)

    # def set(self, key: str, **data) -> None:
    #     self._set(key, **data)

    # def __getattr__(self, key: str) -> Any:
    #     if key in self.model_fields.keys():
    #         return super().__getattr__(key)
    #     return super().__getattr__(key)

    # def __setattr__(self, key: str, value: Any) -> Any:
    #     if key in self.model_fields.keys():
    #         return super().__setattr__(key, value)
    #     return super().__setattr__(key, value)

    # @abstractmethod
    # def _get(self, key: str) -> Setting:
    #     pass

    # @abstractmethod
    # def _set(self, key: str, value: str) -> None:
    #     pass

    # @abstractmethod
    # def _get_all(self) -> Settings:
    #     pass

    # @abstractmethod
    # def _save(self) -> None:
    #     pass

    # def get(self, key: str) -> Setting:
    #     return self._get(key)

    # def set(self, key: str) -> Setting:
    #     return self._set(key)

    # def get_all(self) -> Settings:
    #     return self._get_all()

    # def save(self) -> None:
    #     self._save()


class AwsAppSettings(AppSettings):
    _session: boto3.Session

    def __init__(self, *args, **kwargs):
        super().__init__(*args, _session=boto3.Session(), **kwargs)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, ParameterStoreSettingsSource(settings_cls))


# class AwsAppSettings(AppSettings):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.session = boto3.Session()
#         self.ssm = self.session.client("ssm")

#     @property
#     def namespace(self) -> str:
#         return f"/{self.app}/{self.environment}"

#     def full_key(self, key: str) -> str:
#         return f"{self.namespace}/{key}"

#     def setting_from_parameter(self, param: dict) -> Setting:
#         key: str = param["Name"][len(self.namespace) + 1 :]
#         return Setting(
#             self.namespace, key, param["Value"], param.get("Description", "")
#         )

#     def _get(self, key: str) -> Setting:
#         if key in self._settings:
#             return self._settings[key]
#         response = self.ssm.get_parameter(Name=self.full_key(key))
#         return self.setting_from_parameter(response["Parameter"])

#     def _get_all(self) -> Settings:
#         if self._settings:
#             return self._settings
#         response = self.ssm.get_parameters_by_path(Path=self.namespace, Recursive=True)
#         params = response.get("Parameters", [])
#         for param in params:
#             setting = self.setting_from_parameter(param)
#             self._settings[setting.key] = setting
#         return self._settings

#     def _set(self, key, value, description=""):
#         key = key.strip()
#         if not key:
#             raise Exception("Cannot set an empty key")
#         self._settings[key] = Setting(self.namespace, key, value, description)

#     def _save(self):
#         for key, setting in self._settings.items():
#             full_key = self.full_key(key)
#             self.ssm.put_parameter(
#                 Type="String",
#                 Name=full_key,
#                 Value=setting.value,
#                 Description=setting.description,
#                 Overwrite=True,
#             )
