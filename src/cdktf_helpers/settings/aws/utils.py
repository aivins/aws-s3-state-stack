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

from .defaults import boto3_session


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


def initialise_settings(settings_model, app, environment, dry_run):
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

        current_value_json = None
        if current_value:
            current_value_json = json.dumps(current_value)

        list_input = False
        if get_origin(field.annotation) is list:
            list_input = True

        # Prompt interactively for new value for each key, with defaults
        value = None
        default_msg = f" [{current_value_json}]" if current_value is not None else ""
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
    for key in settings.save(dry_run=dry_run):
        print(f"- {key}")
    if dry_run:
        print("Dry-run mode, nothing saved.")
    else:
        print(
            "\nAll settings saved successfully. Use `aws-app-settings show` to review them."
        )


def show_settings(settings_model, app, environment, _):
    """Pretty print the current paramstore settings for an app/environment"""

    terminal_width = shutil.get_terminal_size().columns
    col_percent_widths = (20, 35, 35, 10)
    col_widths = [
        int(col_width * terminal_width / 100) for col_width in col_percent_widths
    ]

    settings_data = get_all_settings(settings_model, app, environment)

    def wrap(text, width):
        return "\n".join(textwrap.wrap(text, width=width))

    table_data = []
    for key, field in settings_model.get_model_fields(include_computed=True).items():
        exclude = field.exclude if hasattr(field, "exclude") else False
        default = (
            field.default
            if getattr(field, "default", None) not in (None, PydanticUndefined)
            else None
        )
        default = (
            field.default_factory()
            if not default and getattr(field, "default_factory", None)
            else default
        )
        required = field.is_required() if hasattr(field, "is_required") else False
        computed = not hasattr(field, "exclude")
        description = field.description or (
            getattr(field, "json_schema_extra") or {}
        ).get("description", "")

        if exclude:
            continue

        value = settings_data.get(key, None)

        if value is None:
            value = "*missing*"
        elif computed:
            value = f"{value} (computed)"
        elif value == default:
            value = f"{value} (default)"
        else:
            value = str(value)

        table_data.append(
            [
                wrap(key, col_widths[0]),
                wrap(description, col_widths[1]),
                wrap(value, col_widths[2]),
                wrap(str(required), col_widths[3]),
            ]
        )
    headers = ["Setting", "Description", "Value", "Required"]
    print(f"Current settings for {app}/{environment}")
    print(tabulate(table_data, headers=headers, tablefmt="fancy_grid"))


def delete_settings(settings_model, app, environment, dry_run):
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
    for batch in [to_delete[i : i + 10] for i in range(0, len(to_delete), 10)]:
        if not dry_run:
            response = ssm.delete_parameters(Names=batch)
            deleted.extend(response.get("DeletedParameters", []))
            invalid.extend(response.get("InvalidParameters", []))
    if dry_run:
        print("Dry-run mode, nothing deleted.")
    else:
        print(f"Deleted {len(deleted)} of {len(to_delete)} parameters")
        print(f"Also saved a backup as {backup_file_name}")
        if invalid:
            print("Deletion failed for the following parameters")
            for name in invalid:
                print(f"- {name}")


def run_cdktf_app(
    app_name, environment, settings_model, *stack_classes, create_state_resources=False
):
    from cdktf_helpers.apps import AwsApp

    print(f"Using settings model {settings_model.__name__}")

    try:
        settings = settings_model(app_name, environment)
    except ValidationError as e:
        print("Settings failed validation:")
        for error in e.errors():
            key = error["loc"][0]
            pos = f".{error['loc'][1]}" if len(error["loc"]) > 1 else ""
            msg = error["msg"]
            input = error["input"]
            path = f"{settings_model.__module__}.{settings_model.__qualname__}"
            print(f"- {key}{pos}: {msg} (input: {input})")
            print(
                "\nYou can review your settings with "
                f"`aws-app-settings show {app_name} {environment}` or "
                f"update them with `aws-app-settings init {app_name} {environment} "
                f"--settings-model {path}`"
            )
        sys.exit(1)

    app = AwsApp(settings)

    print(
        f"Running CDKTF app {app_name}/{environment} with settings {settings_model.__name__}"
    )

    for stack_class in stack_classes:
        stack_class(
            app, stack_class.__name__, create_state_resources=create_state_resources
        )
        print(f"Added {stack_class.__name__} to app")

    app.synth()
