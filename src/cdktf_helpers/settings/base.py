from pydantic import BaseModel, Field, computed_field
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Setting(BaseModel):
    value: str
    description: str = ""


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

    def set(self, key, value, description=""):
        key = key.strip()
        if not key:
            raise Exception("Cannot set an empty key")
        if key not in self.model_fields:
            raise Exception(f"{key} is not a field on {self.__class__.__name__}")
        field = self.model_fields[key]
        setattr(self, key, field.annotation(value=value, description=description))

    def save(self):
        pass
