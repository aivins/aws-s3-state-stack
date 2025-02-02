import json
from typing import Tuple, Type, TypeVar

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from ..base import AppSettings
from .utils import boto3_session


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
                source["app"], source["environment"], self.settings_cls
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

    def save(self, dry_run=False):
        ssm = boto3_session().client("ssm")
        saved = []
        for key, field in self.get_model_fields(include_computed=True).items():
            full_key = f"{self.namespace}/{key}"
            value = json.dumps(getattr(self, key))
            description = field.description or ""
            if not dry_run:
                ssm.put_parameter(
                    Type="String",
                    Name=full_key,
                    Value=value,
                    Description=description,
                    Overwrite=True,
                )
            saved.append(key)
        return saved


AwsAppSettingsType = TypeVar("T", bound=AwsAppSettings)
