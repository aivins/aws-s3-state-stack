import argparse
import sys

from botocore.exceptions import UnauthorizedSSOTokenError

from .backends import AutoS3Backend
from .settings.utils import (
    delete_settings,
    get_settings_model,
    initialise_settings,
    show_settings,
)


def get_settings_cli_args():
    return (
        ("action", {"choices": ("show", "init", "delete")}),
        ("app", {}),
        ("environment", {}),
        ("--settings-model", {"default": None}),
    )


def get_create_backend_resources_cli_args():
    return (
        ("s3_bucket_name", {"help": "Name of S3 bucket to create"}),
        ("dynamodb_table_name", {"help": "Name of DynamoDB table to create"}),
    )


def settings_cli_entrypoint():
    parser = argparse.ArgumentParser(
        description="Initialise, update, and show AwsAppSettings in ParameterStore"
    )
    for name, params in get_settings_cli_args():
        parser.add_argument(name, **params)
    options = parser.parse_args()
    settings_model = get_settings_model(options.settings_model)
    if not settings_model:
        if not options.settings_model:
            print(
                "Could not determine your settings model automatically. "
                "Use --settings-model"
            )
        else:
            print(f"Could not load settings model {options.settings_model}")
        exit(1)

    actions = {
        "show": show_settings,
        "init": initialise_settings,
        "delete": delete_settings,
    }

    try:
        actions[options.action](settings_model, options.app, options.environment)
    except UnauthorizedSSOTokenError:
        print(
            "Looks like you don't have a valid AWS SSO session. "
            "Start one with `aws sso login` or manually configure your "
            "environment before trying again."
        )
        sys.exit(1)


def create_backend_resources_cli_entrypoint():
    parser = argparse.ArgumentParser(
        description="Create S3/DyanamoDB Terraform Backend resources if they don't already exist"
    )
    for name, params in get_create_backend_resources_cli_args():
        parser.add_argument(name, **params)
    options = parser.parse_args()
    AutoS3Backend.ensure_backend_resources(**vars(options))
