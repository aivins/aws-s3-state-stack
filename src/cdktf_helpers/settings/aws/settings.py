import json
from typing import Tuple, Type, TypeVar, get_origin

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from ..base import AppSettings
from .types import AwsResource, AwsResources, NestedResourceMixin
from .utils import boto3_session


def fetch_settings(prefix):
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


class ParameterStoreSettingsSource(PydanticBaseSettingsSource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._params = None

    def fetch_params(self) -> None:
        if self._params:
            return self._params
        source = self.settings_sources_data["InitSettingsSource"]
        app = source["app"]
        environment = source["environment"]
        prefix = self.settings_cls.format_namespace(app, environment)
        ssm = boto3_session().client("ssm")
        paginator = ssm.get_paginator("get_parameters_by_path")
        pages = paginator.paginate(Path=prefix, Recursive=True)
        params = {}
        for page in pages:
            for param in page.get("Parameters", []):
                field_name = param["Name"][len(prefix) :]
                value = param["Value"]
                params[field_name] = json.loads(value)
        self._params = params
        return self._params

    def get_field_value(self, field, field_name):
        # We don't seem to end up calling this at all, but it's
        # required by the ABC. Throw out a message in case this
        # ends up being wrong
        assert False, (
            "ParameterStoreSettingsSource.get_field_value() "
            "not implemented and called unexpectedly"
        )

    def __call__(self):
        params = self.fetch_params()
        settings = {}
        for field_name, _ in self.settings_cls.model_fields.items():
            if field_name in params:
                settings[field_name] = params[field_name]
        return settings


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

    @classmethod
    def fetch_settings(cls, app, environment):
        prefix = cls.format_namespace(app, environment)
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
