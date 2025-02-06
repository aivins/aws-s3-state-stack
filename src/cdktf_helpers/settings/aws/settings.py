import json
from typing import Tuple, Type, TypeVar, get_origin

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from ..base import AppSettings
from .types import AwsResource, AwsResources, NestedResourceMixin
from .utils import boto3_session


class ParameterStoreSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls, *args, **kwargs):
        super().__init__(settings_cls, *args, **kwargs)
        self._settings = None

    def fetch_settings(self, app, environment):
        prefix = self.settings_cls.format_namespace(app, environment)
        ssm = boto3_session().client("ssm")
        paginator = ssm.get_paginator("get_parameters_by_path")
        pages = paginator.paginate(Path=prefix, Recursive=True)
        settings = {}
        for page in pages:
            for param in page.get("Parameters", []):
                field_name = param["Name"][len(prefix) :]
                value = json.loads(param["Value"])
                settings[field_name] = value
        return settings

    def get_field_value(self, field, field_name):
        if field.exclude or field_name not in self._settings:
            return None, "", False

        return (
            self._settings[field_name],
            field_name,
            True,
        )

    def __call__(self):
        source = self.settings_sources_data["InitSettingsSource"]
        app = source["app"]
        environment = source["environment"]
        if not self._settings:
            self._settings = self.fetch_settings(app, environment)
        for field_name, field in self.settings_cls.model_fields.items():
            field_value, field_key, value_is_complex = self.get_field_value(
                field, field_name
            )
            if field_key:
                self._settings[field_key] = field_value
        return self._settings


class AwsAppSettings(NestedResourceMixin, AppSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        *args,
        **kwargs,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, ParameterStoreSettingsSource(settings_cls))

    def serialize_value(self, field_name):
        value = getattr(self, field_name)
        if field_name in self.model_fields:
            field = self.model_fields[field_name]
            origin = get_origin(field.annotation) or field.annotation
            if issubclass(origin, AwsResources):
                if not isinstance(value, AwsResources):
                    raise TypeError(
                        f"{field} name should be an AwsResources collection "
                        f"object, not {type(value).__name__}"
                    )
                value = value.ids
            elif issubclass(origin, AwsResource):
                if not isinstance(value, AwsResource):
                    raise TypeError(
                        f"{field} name should be an AwsResource object, "
                        f"not {type(value).__name__}"
                    )
                value = str(value)
        return json.dumps(value)

    def save(self, dry_run=False):
        ssm = boto3_session().client("ssm")
        saved = []
        for key, field in self.get_model_fields(include_computed=True).items():
            full_key = f"{self.namespace}{key}"
            value = self.serialize_value(key)
            description = field.description
            if not description:
                description = (
                    field.json_schema_extra.get("description", "")
                    if field.json_schema_extra
                    else ""
                )
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
