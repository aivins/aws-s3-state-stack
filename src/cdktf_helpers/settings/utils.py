import importlib
import json
import math
import re
import shutil
import sys
import textwrap
from typing import get_origin

from pydantic import TypeAdapter, ValidationError
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


def fetch_settings(namespace):
    ssm = boto3_session().client("ssm")
    paginator = ssm.get_paginator("get_parameters_by_path")
    pages = paginator.paginate(Path=namespace, Recursive=True)
    for page in pages:
        for param in page.get("Parameters", []):
            yield param


def get_all_settings(settings_model, app, environment):
    """Fetch all settings for the given settings model and app/environemnt from parameterstore"""

    namespace = settings_model.format_namespace(app, environment)
    settings = {}
    for param in fetch_settings(namespace):
        key = param["Name"][len(namespace) + 1 :]
        value = param["Value"]
        settings[key] = json.loads(value)
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
    namespace = settings_model.format_namespace(app, environment)
    settings = fetch_settings(namespace)
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
            elif field.default_factory:
                current_value = field.default_factory()

        if current_value:
            current_value = json.dumps(current_value)

        list_input = False
        if get_origin(field.annotation) is list:
            list_input = True

        # Prompt interactively for new value for each key, with defaults
        value = None
        default_msg = f" [{current_value}]" if current_value is not None else ""
        list_msg = " as JSON list" if list_input else ""

        print(f"{field.description} ({key})" or key)
        while value in (None, ""):
            value = input(f"Enter value{list_msg}{default_msg}: ").strip()
            if not value and current_value is not None:
                value = current_value
            else:
                validator = TypeAdapter(field.annotation)
                try:
                    if list_input:
                        value = validator.validate_json(value)
                    else:
                        value = validator.validate_strings(value)
                except ValidationError as e:
                    if "invalid json" in str(e).lower() and list_input:
                        print('Invalid list input. Try: ["val1","val2","val3"]')
                    else:
                        print(", ".join([x["msg"] for x in e.errors()]))
                    value = None
                    continue
        print()
        updated[key] = value

    settings = settings_model(app=app, environment=environment, **updated)

    # Update paramstore with new values
    namespace = settings_model.format_namespace(app, environment)
    print(f"Saving settings to ParamterStore under '{namespace}'...\n")
    for key in settings.save():
        print(f"- {key}")
    print(
        "\nAll settings saved successfully. Use `aws-app-settings show` to review them."
    )


def show_settings(settings_model, app, environment):
    """Pretty print the current paramstore settings for an app/environment"""

    terminal_width = shutil.get_terminal_size().columns
    col_percent_widths = (20, 35, 35, 10)
    col_widths = [
        int(col_width * terminal_width / 100) for col_width in col_percent_widths
    ]

    settings_data = get_all_settings(settings_model, app, environment)
    data = []

    # Create a dummy settings instance to render computed fields
    settings = settings_model.model_construct(**settings_data)

    def wrap(text, width):
        return "\n".join(textwrap.wrap(text, width=width))

    all_fields = {**settings_model.model_fields, **settings_model.model_computed_fields}

    for key, field in all_fields.items():
        if key == "namespace":
            continue
        exclude = field.exclude if hasattr(field, "exclude") else False
        default = field.default if hasattr(field, "default") else None
        required = field.is_required() if hasattr(field, "is_required") else False
        computed = not hasattr(field, "exclude")

        if exclude:
            continue

        value = str(getattr(settings, key))

        if value is None:
            value = "*missing*"
        elif computed:
            value = f"{value} (computed)"
        elif value == default:
            value = f"{value} (default)"

        data.append(
            [
                wrap(key, col_widths[0]),
                wrap(field.description or "", col_widths[1]),
                wrap(value, col_widths[2]),
                wrap(str(required), col_widths[3]),
            ]
        )
    headers = ["Setting", "Description", "Value", "Required"]
    print(f"Current settings for {app}/{environment}")
    print(tabulate(data, headers=headers, tablefmt="fancy_grid"))


def delete_settings(settings_model, app, environment):
    namespace = settings_model.format_namespace(app, environment)

    print(f"\nWARNING! You are about to delete all settings for {namespace}!")
    confirm = input("Are you really sure you want to do this? [y/N]: ")
    if not confirm.lower().startswith("y"):
        print("Aborted!")
        sys.exit()

    print("Determining list of settings to delete...")
    to_delete = []
    backup = {}
    for param in fetch_settings(namespace):
        to_delete.append(param["Name"])
        backup[param["Name"]] = param["Value"]

    if not len(to_delete):
        print(f"Nothing settings found to delete under {namespace}")
        sys.exit()

    print(
        "Last chance to back out! This will permanently delete "
        f"{len(to_delete)} settings from {namespace}!"
    )
    confirm = input("Are you really, REALLY sure? [y/N]: ")
    if not confirm.lower().startswith("y"):
        print("Aborted. Aren't you glad that there was a second confirmation?")
        sys.exit()

    backup_file_name = f"{app}-{environment}-aws-settings.json"
    with open(backup_file_name, "w") as fh:
        json.dump(backup, fh, indent=2)

    ssm = boto3_session().client("ssm")
    deleted = []
    invalid = []
    # API limits us to deleting in batches of 10
    for i in range(math.ceil(len(to_delete) / 10)):
        batch = to_delete[i : min(10, len(to_delete) - i)]
        response = ssm.delete_parameters(Names=batch)
        deleted.extend(response.get("DeletedParameters", []))
        invalid.extend(response.get("InvalidParameters", []))
    print(f"Deleted {len(deleted)} of {len(to_delete)} parameters")
    print(f"Also saved a backup as {backup_file_name}")
    if invalid:
        print("Deletion failed for the following parameters")
        for name in invalid:
            print(f"- {name}")
