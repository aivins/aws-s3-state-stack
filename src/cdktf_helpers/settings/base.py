import functools
from typing import Any, TypeVar

from pydantic import Field
from pydantic import computed_field as pydantic_computed_field
from pydantic_core import PydanticUndefined
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


def computed_field(arg, description="x", json_schema_extra={}, **kwargs):
    @functools.wraps(pydantic_computed_field)
    def wrapper(func=None):
        def wrapped():
            return pydantic_computed_field(
                json_schema_extra={
                    "description": arg or description,
                    **json_schema_extra,
                },
                **kwargs,
            )(func)

        return wrapped()

    if callable(arg):
        return wrapper(arg)

    return wrapper


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", populate_by_name=True)
    app: str
    environment: str

    _hidden_fields: list[str] = ["app", "environment", "namespace"]

    @classmethod
    def get_hidden_fields(cls):
        return cls._hidden_fields.default

    @pydantic_computed_field
    @property
    def namespace(self) -> str:
        return self.format_namespace(self.app, self.environment)

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

    @classmethod
    def get_model_fields(cls, include_computed=False):
        hidden_fields = cls.get_hidden_fields()
        model_fields = {
            **cls.model_fields,
            **(cls.model_computed_fields if include_computed else {}),
        }
        return {k: v for k, v in model_fields.items() if k not in hidden_fields}

    @classmethod
    def format_namespace(cls, app: str, environment: str) -> str:
        return f"/{app}/{environment}/"

    def serialize_value(self, field_name):
        return getattr(self, field_name)

    def get_description(self, key):
        return self.model_fields[key].description or ""

    def save(self, dry_run=False):
        pass

    def as_dict(self, prefix=""):
        return {
            k: getattr(self, k)
            for k in self.get_model_fields(include_computed=True)
            if k.startswith(prefix)
        }

    def as_env(self, prefix=""):
        def value(v):
            return str(v).lower() if isinstance(v, bool) else v

        return [
            {"name": k.upper(), "value": value(v)}
            for k, v in self.as_dict(prefix).items()
        ]


AppSettingsType = TypeVar("AppSettingsType", bound=AppSettings)
