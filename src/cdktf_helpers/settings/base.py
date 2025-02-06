import functools
from typing import List, TypeVar

from pydantic import Field
from pydantic import computed_field as pydantic_computed_field
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
    def get_hidden_fields(self):
        return self._hidden_fields

    @pydantic_computed_field
    @property
    def namespace(self) -> str:
        return self.format_namespace(self.app, self.environment)

    @classmethod
    def model_dict(cls, app: str, environment: str, **kwargs):
        return cls.model_construct(
            app=app, environment=environment, **kwargs
        ).model_dump(exclude=["namespace"])

    @classmethod
    def get_model_fields(cls, include_computed=False):
        model_fields = {k: v for k, v in cls.model_fields.items() if not v.exclude}
        if include_computed:
            model_fields = {**model_fields, **cls.model_computed_fields}
        model_fields.pop("namespace", None)
        return model_fields

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
