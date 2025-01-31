import base64
import hashlib


def unique_name(input_string: str) -> str:
    digest = hashlib.sha256(input_string.encode()).digest()
    return f"{input_string}-" + base64.urlsafe_b64encode(digest).decode()[:8].lower()
