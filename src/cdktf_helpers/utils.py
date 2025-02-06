import base64
import hashlib

from pydantic_core import PydanticUndefined


def unique_name(input_string: str) -> str:
    digest = hashlib.sha256(input_string.encode()).digest()
    return f"{input_string}-" + base64.urlsafe_b64encode(digest).decode()[:8].lower()


def extract_default(field):
    default = getattr(field, "default", PydanticUndefined)
    if default is not PydanticUndefined:
        return default
    default_factory = getattr(field, "default_factory", None)
    if default_factory:
        return default_factory()
