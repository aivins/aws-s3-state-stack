import argparse

from .backends import AutoS3Backend
from .settings.utils import get_settings_model, initialise_settings, show_settings


def get_settings_cli_args():
    return (
        ("action", {"choices": ("show", "init")}),
        ("app", {}),
        ("environemnt", {}),
        ("--settings-modek", {"default": None}),
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
    # for name, params in get_settings_cli_args():
    #     parser.add_argument(name, **params)
    parser.add_argument("action", choices=("show", "init"))
    parser.add_argument("app")
    parser.add_argument("environment")
    parser.add_argument("--settings-model", default=None)
    options = parser.parse_args()
    settings_model = get_settings_model(options.settings_model)
    if options.action == "show":
        show_settings(settings_model, options.app, options.environment)
    elif options.action == "init":
        initialise_settings(settings_model, options.app, options.environment)


def create_backend_resources_cli_entrypoint():
    parser = argparse.ArgumentParser(
        description="Create S3/DyanamoDB Terraform Backend resources if they don't already exist"
    )
    # for name, params in get_create_backend_resources_cli_args():
    #     parser.add_argument(name, **params)
    parser.add_argument("s3_bucket_name", help="Name of S3 bucket to create")
    parser.add_argument("dynamodb_table_name", help="Name of DynamoDB table to create")
    options = parser.parse_args()
    AutoS3Backend.ensure_backend_resources(**vars(options))
