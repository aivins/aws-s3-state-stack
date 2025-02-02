import argparse
import importlib
import os
import sys

from botocore.exceptions import UnauthorizedSSOTokenError

from .backends import AutoS3Backend
from .settings.aws import (
    delete_settings,
    initialise_settings,
    run_cdktf_app,
    show_settings,
)


def import_from_string(path):
    module_name, symbol_name = path.rsplit(".")
    try:
        sys.path.insert(0, "")
        module = importlib.import_module(module_name)
        sys.path.pop(0)
        return getattr(module, symbol_name)
    except (ImportError, AttributeError) as e:
        print(f"Could not import {symbol_name} from {module_name}: {e}")
        sys.exit(1)


def get_settings_model(class_path=None):
    """Load a settings model class if provided, else try to find it in cdktf_settings.py"""
    from .settings.aws import AwsAppSettings

    settings_model = None
    if class_path:
        settings_model = import_from_string(class_path)
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

    if not settings_model:
        if not class_path:
            print(
                "Could not determine your settings model automatically. "
                "Use --settings-model"
            )
        else:
            print(f"Could not load settings model {class_path}")
        sys.exit(1)
    return settings_model


app_arg = ("app", {})
environment_option = (
    "--environment",
    {
        "default": os.environ.get("CDKTF_APP_ENVIRONMENT"),
        "required": not os.environ.get("CDKTF_APP_ENVIRONMENT"),
    },
)
settings_model_option = ("--settings-model", {"default": None})


def get_settings_cli_args():
    return (
        ("action", {"choices": ("show", "init", "delete")}),
        app_arg,
        environment_option,
        settings_model_option,
        ("--dry-run", {"action": "store_true"}),
    )


def get_create_backend_resources_cli_args():
    return (
        ("s3_bucket_name", {"help": "Name of S3 bucket to create"}),
        ("dynamodb_table_name", {"help": "Name of DynamoDB table to create"}),
    )


def get_app_args():
    return (
        app_arg,
        environment_option,
        (
            "stacks",
            {
                "nargs": "+",
                "help": "Python class path to stack(s) (eg. path.to.module.StackClass)",
            },
        ),
        settings_model_option,
    )


def settings_cli_entrypoint():
    parser = argparse.ArgumentParser(
        description="Initialise, update, and show AwsAppSettings in ParameterStore"
    )
    for name, params in get_settings_cli_args():
        parser.add_argument(name, **params)
    options = parser.parse_args()
    settings_model = get_settings_model(options.settings_model)

    actions = {
        "show": show_settings,
        "init": initialise_settings,
        "delete": delete_settings,
    }

    try:
        actions[options.action](
            settings_model, options.app, options.environment, options.dry_run
        )
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


def app_entrypoint():
    parser = argparse.ArgumentParser("Entrypoint for CDKTF Application")
    for name, params in get_app_args():
        parser.add_argument(name, **params)
    options = parser.parse_args()
    settings_model = get_settings_model(options.settings_model)
    stack_classes = [import_from_string(path) for path in options.stacks]
    run_cdktf_app(options.app, options.environment, settings_model, *stack_classes)
