import argparse
import importlib
import re
import textwrap
from typing import get_origin

import tabulate

from cdktf_helpers.backends import AutoS3Backend

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
    response = ssm.describe_parameters(
        ParameterFilters=[
            {
                "Key": "Name",
                "Option": "BeginsWith",
                "Values": [
                    namespace,
                ],
            },
        ]
    )
    descriptions = {p["Name"]: p.get("Description", "") for p in response["Parameters"]}
    response = ssm.get_parameters_by_path(Path=namespace, Recursive=True)
    params = response.get("Parameters", [])
    settings = {}
    for param in params:
        description = descriptions[param["Name"]]
        key = param["Name"][len(namespace) + 1 :]
        value = param["Value"]
        if key in settings_model.model_fields:
            field = settings_model.model_fields[key]
            if get_origin(field.annotation.model_fields["value"].annotation) is list:
                value = [v.replace("\\", "") for v in re.split(r"(?<!\\),", value)]
            settings[key] = field.annotation(value=value, description=description)
    return settings


def get_settings_model(class_path=None):
    """Load a settings model class if provided, else try to find it in a cdktf main.py"""

    settings_model = None
    if class_path:
        module_name, class_name = class_path.rsplit(".")
        module = importlib.import_module(module_name)
        settings_model = getattr(module, class_name)
    else:
        try:
            main = importlib.import_module("main")
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
            default_value = settings[key].value
        else:
            default_value = None

        # Use the description from the model, ignore any difference in paramstore
        description = ""
        description_field = field.annotation.model_fields["description"]
        if description_field.default:
            description = description_field.default

        # Prompt interactively for new value for each key, with defaults
        value = None
        while not value:
            default_msg = f" [{default_value}]" if default_value is not None else ""
            field_id = f"{description} ({key})" if description else key
            value = input(f"{field_id}{default_msg}: ")
            if not value and default_value:
                value = default_value
        updated[key] = field.annotation(value=value, description=description)

    settings = settings_model(app=app, environment=environment, **updated)

    # Update paramstore with new values
    settings.save()


def show_settings(settings_model, app, environment):
    """Pretty print the current paramstore settings for an app/environment"""

    settings = fetch_settings(settings_model, app, environment)
    data = []

    def wrap(text, width):
        return "\n".join(textwrap.wrap(text, width=width))

    for key, field in settings_model.model_fields.items():
        if field.exclude:
            continue
        setting = settings.get(key, None)
        value = getattr(setting, "value", None)
        description = ""
        required = True
        default_value = None
        if hasattr(field.annotation, "model_fields"):
            description = field.annotation.model_fields["description"].default
            required = field.annotation.model_fields["value"].is_required()
            default_factory = field.annotation.model_fields["value"].default_factory
            if default_factory:
                default_value = default_factory()

        default = False
        if default_value and default_value == value:
            default = True

        if isinstance(value, list):
            value = ",".join([v.replace(",", "\,") for v in setting.value])

        if not value:
            value = "*missing*"

        if default:
            value = f"{value} (default)"

        data.append([wrap(key, 24), wrap(description, 24), wrap(value, 52), required])
    headers = ["Setting", "Description", "Value", "Required"]
    print(f"Current settings for {app}/{environment}")
    print(tabulate(data, headers=headers, tablefmt="fancy_grid"))
