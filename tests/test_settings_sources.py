import json
from typing import Any

from moto import mock_aws
from pydantic_core import PydanticUndefined
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
)

from cdktf_helpers.settings.aws.utils import boto3_session


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


class Settings(BaseSettings):
    app: str
    environment: str
    first_name: str
    last_name: str
    age: int
    children: list[str]
    nationality: str = "Strayan"

    @classmethod
    def format_namespace(cls, app: str, environment: str):
        return f"/{app}/{environment}/"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        *args,
        **kwargs,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, ParameterStoreSettingsSource(settings_cls))

    @classmethod
    def settings_dict(
        cls, app: str, environment: str, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        partial_settings = super().model_construct(*args, **kwargs)
        source_data = partial_settings._settings_build_values(
            {"app": app, "environment": environment}
        )
        settings = {}
        for field_name, field in cls.model_fields.items():
            value = source_data.get(field_name, None)
            if value is None:
                if field.default is not PydanticUndefined:
                    value = field.default
                elif field.default_factory:
                    value = field.default_factory()
            settings[field_name] = value
        return settings


def create_paramstore_entries(**data):
    ssm = boto3_session().client("ssm")
    for key, value in data.items():
        full_key = f"/testapp/dev/{key}"
        ssm.put_parameter(
            Type="String",
            Name=full_key,
            Value=json.dumps(value),
            Description="",
            Overwrite=True,
        )


def test_paramstore_source():
    with mock_aws():
        create_paramstore_entries(
            first_name="Andy",
            age=46,
            children=["Hayden", "Ashleigh"],
        )
        settings = Settings.settings_dict(app="testapp", environment="dev")
        # Fetched from paramstore
        assert settings["first_name"] == "Andy"
        # Default from model
        assert settings["nationality"] == "Strayan"
        # Should be None without validation failures until later
        assert settings["last_name"] is None
