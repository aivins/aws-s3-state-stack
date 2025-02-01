import importlib
import json
import re
import shutil
import sys
import textwrap
from typing import get_origin

from pydantic_core import PydanticUndefined
from tabulate import tabulate

from .aws import AwsAppSettings, boto3_session


def ensure_backend_resources(s3_bucket_name, dynamodb_table_name):
    assert s3_bucket_name
    assert dynamodb_table_name
    session = boto3_session()
    s3 = session.resource("s3")
    dynamodb = session.resource("dynamodb")
    for bucket in s3.buckets.all():
        if bucket.name == s3_bucket_name:
            break
    else:
        bucket = s3.create_bucket(
            Bucket=s3_bucket_name,
            CreateBucketConfiguration={"LocationConstraint": session.region_name},
        )
    for table in dynamodb.tables.all():
        if table.name == dynamodb_table_name:
            break
    else:
        table = dynamodb.create_table(
            TableName=dynamodb_table_name,
            KeySchema=[
                {
                    "AttributeName": "LockID",
                    "KeyType": "HASH",
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName": "LockID",
                    "AttributeType": "S",
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )


def fetch_settings(settings_model, app, environment):
    """Fetch all settings for the given settings model and app/environemnt from parameterstore"""

    namespace = settings_model.format_namespace(app, environment)
    ssm = boto3_session().client("ssm")
    response = ssm.get_parameters_by_path(Path=namespace, Recursive=True)
    params = response.get("Parameters", [])
    settings = {}
    for param in params:
        key = param["Name"][len(namespace) + 1 :]
        value = param["Value"]
        if key in settings_model.model_fields:
            field = settings_model.model_fields[key]
            if get_origin(field.annotation) is list:
                value = [v.replace("\\", "") for v in re.split(r"(?<!\\),", value)]
            settings[key] = value
    return settings


def get_settings_model(class_path=None):
    """Load a settings model class if provided, else try to find it in cdktf_settings.py"""

    settings_model = None
    if class_path:
        module_name, class_name = class_path.rsplit(".")
        module = importlib.import_module(module_name)
        settings_model = getattr(module, class_name)
    else:
        try:
            sys.path.insert(0, ".")
            main = importlib.import_module("cdktf_settings")
            sys.path.pop(0)
            settings_models = [
                obj
                for obj in vars(main).values()
                if isinstance(obj, type) and issubclass(obj, AwsAppSettings)
            ]
            if settings_models:
                settings_model = settings_models[0]
                for item in settings_models:
                    if len(item.mro()) > len(settings_model.mro()):
                        settings_model = item
        except ImportError:
            pass
    return settings_model


def initialise_settings(settings_model, app, environment):
    """Interactive CLI prompts to initialise or update paramater store settings"""
    settings = fetch_settings(settings_model, app, environment)
    updated = {}
    for key, field in settings_model.model_fields.items():
        if field.exclude:
            continue
        # Default to the current value, which is either from paramstore
        # or automatically applied as a setting default
        if key in settings:
            current_value = settings[key]
        else:
            current_value = None

        if current_value is None:
            if field.default is not PydanticUndefined:
                current_value = field.default

        # Prompt interactively for new value for each key, with defaults
        value = None
        default_msg = f" [{current_value}]" if current_value is not None else ""
        print(f"{field.description} ({key})" or key)
        while value in (None, ""):
            value = input(f"Enter value{default_msg}:").strip()
            if not value and current_value is not None:
                value = current_value
            else:
                try:
                    if value:
                        value = json.loads(value)
                except json.JSONDecodeError:
                    pass
        print()
        updated[key] = value

    settings = settings_model(app=app, environment=environment, **updated)

    # Update paramstore with new values
    namespace = settings_model.format_namespace(app, environment)
    print(f"Saving settings to ParamterStore under {namespace}")
    for key in settings.save():
        print(f"- Wrote {key}")


def show_settings(settings_model, app, environment):
    """Pretty print the current paramstore settings for an app/environment"""

    terminal_width = shutil.get_terminal_size().columns
    col_percent_widths = (20, 35, 35, 10)
    col_widths = [
        int(col_width * terminal_width / 100) for col_width in col_percent_widths
    ]

    settings = fetch_settings(settings_model, app, environment)
    data = []

    def wrap(text, width):
        return "\n".join(textwrap.wrap(text, width=width))

    for key, field in settings_model.model_fields.items():
        if field.exclude:
            continue
        value = settings.get(key, None)

        if isinstance(value, list):
            value = ",".join([v.replace(",", r"\,") for v in value])

        if not value:
            value = "*missing*"

        if value == field.default:
            value = f"{value} (default)"

        data.append(
            [
                wrap(key, col_widths[0]),
                wrap(field.description or "", col_widths[1]),
                wrap(value, col_widths[2]),
                wrap(str(field.is_required()), col_widths[3]),
            ]
        )
    headers = ["Setting", "Description", "Value", "Required"]
    print(f"Current settings for {app}/{environment}")
    print(tabulate(data, headers=headers, tablefmt="fancy_grid"))
