import functools
from typing import TypeVar

from pydantic import Field
from pydantic import computed_field as pydantic_computed_field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


def computed_field(*args, **kwargs):
    description = kwargs.get("description", "")
    json_schema_extra = kwargs.get("json_schema_extra", {})

    @functools.wraps(pydantic_computed_field)
    def wrapper(func=None):
        def wrapped():
            return pydantic_computed_field(
                json_schema_extra={"description": description, **json_schema_extra},
                **kwargs,
            )(func)

        return wrapped()

    if len(args) == 1 and callable(args[0]) and not kwargs:
        return wrapper(args[0])

    return wrapper


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", populate_by_name=True)
    app: str = Field(exclude=True, default="app")
    environment: str = Field(exclude=True, default="dev")

    def __init__(self, app: str, environment: str, **kwargs):
        super().__init__(app=app, environment=environment, **kwargs)

    @pydantic_computed_field
    @property
    def namespace(self) -> str:
        return self.format_namespace(self.app, self.environment)

    @classmethod
    def get_model_fields(cls, include_computed=False):
        model_fields = {k: v for k, v in cls.model_fields.items() if not v.exclude}
        if include_computed:
            model_fields = {**model_fields, **cls.model_computed_fields}
        model_fields.pop("namespace", None)
        return model_fields

    @classmethod
    def format_namespace(cls, app: str, environment: str) -> str:
        return f"/{app}/{environment}"

    def get_description(self, key):
        return self.model_fields[key].description or ""

    def save(self, dry_run=False):
        pass


AppSettingsType = TypeVar("AppSettingsType", bound=AppSettings)
