import functools

from pydantic import BaseModel, Field
from pydantic import computed_field as computed_field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


def custom_computed_field(description="", json_schema_extra={}, **kwargs):
    """Custom wrapper for computed_field that ensures it remains a property."""

    @functools.wraps(computed_field)
    def wrapper(func=None):
        def wrapped():
            return computed_field(
                json_schema_extra={"description": description, **json_schema_extra},
                **kwargs,
            )(func)

        return wrapped()

    return wrapper


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", populate_by_name=True)
    app: str = Field(exclude=True, default="app")
    environment: str = Field(exclude=True, default="dev")

    @computed_field
    @property
    def namespace(self) -> str:
        return self.format_namespace(self.app, self.environment)

    @classmethod
    def format_namespace(cls, app: str, environment: str) -> str:
        return f"/{app}/{environment}"

    def get_description(self, key):
        return self.model_fields[key].description or ""

    def save(self):
        pass
