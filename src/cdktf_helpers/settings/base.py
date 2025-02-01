from pydantic import BaseModel, Field, computed_field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", populate_by_name=True)
    app: str = Field(exclude=True, default="app")
    environment: str = Field(exclude=True, default="dev")

    @computed_field
    def namespace(self) -> str:
        return self.format_namespace(self.app, self.environment)

    @classmethod
    def format_namespace(cls, app: str, environment: str) -> str:
        return f"/{app}/{environment}"

    def get_description(self, key):
        return self.model_fields[key].description or ""

    def save(self):
        pass
