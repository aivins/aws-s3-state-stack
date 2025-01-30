from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, TypeAlias

import boto3


@dataclass
class Setting:
    namespace: str
    key: str
    value: str
    description: str = ""

    def __str__(self) -> str:
        return self.value


Settings = Dict[str, Setting]


class AppSettings(ABC):
    settings_class = Settings

    def __init__(self, app: str, environment: str):
        self.app = app
        self.environment = environment
        self._settings: self.settings_class = {}

    @property
    @abstractmethod
    def namespace(self) -> str:
        pass

    @abstractmethod
    def get(self, key: str) -> str:
        pass

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        pass

    @abstractmethod
    def get_all(self) -> Settings:
        pass

    def get_keys(self):
        return self.settings_class.__annotations__


class AwsAppSettings(AppSettings):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = boto3.Session()
        self.ssm = self.session.client("ssm")

    @property
    def namespace(self) -> str:
        return f"/{self.app}/{self.environment}"

    def full_key(self, key: str) -> str:
        return f"{self.namespace}/{key}"

    def setting_from_parameter(self, param: dict) -> Setting:
        key: str = param["Name"][len(self.namespace) + 1 :]
        return Setting(
            self.namespace, key, param["Value"], param.get("Description", "")
        )

    def get(self, key: str) -> Setting:
        if key in self._settings:
            return self._settings[key]
        response = self.ssm.get_parameter(Name=self.full_key(key))
        return self.setting_from_parameter(response["Parameter"])

    def get_all(self) -> Settings:
        if self._settings:
            return self._settings
        response = self.ssm.get_parameters_by_path(Path=self.namespace, Recursive=True)
        params = response.get("Parameters", [])
        for param in params:
            setting = self.setting_from_parameter(param)
            self._settings[setting.key] = setting
        return self._settings

    def set(self, key, value, description=""):
        key = key.strip()
        if not key:
            raise Exception("Cannot set an empty key")
        self._settings[key] = Setting(self.namespace, key, value, description)

    def save(self):
        for key, setting in self._settings.items():
            full_key = self.full_key(key)
            self.ssm.put_parameter(
                Type="String",
                Name=full_key,
                Value=setting.value,
                Description=setting.description,
                Overwrite=True,
            )
