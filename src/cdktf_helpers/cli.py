import argparse
import importlib
import os
import sys
from dataclasses import dataclass
from typing import Annotated, List, Optional

import typer
from botocore.exceptions import UnauthorizedSSOTokenError
from rich import print

from .backends import AutoS3Backend
from .settings.aws import (
    delete_settings,
    ensure_backend_resources,
    initialise_settings,
    run_cdktf_app,
    show_settings,
)


def import_from_string(path):
    sys.path.insert(0, "")
    try:
        try:
            module = importlib.import_module(path)
            cls = None
        except ImportError:
            path, class_name = path.rsplit(".")
            module = importlib.import_module(path)
            cls = getattr(module, class_name, None)
    except (ImportError, AttributeError) as e:
        print(f"Could not import {path}: {e}")
        sys.exit(1)
    sys.path.pop(0)
    return (module, cls)


def import_stack_from_string(path):
    (module, cls) = import_from_string(path)
    if cls is None:
        cls = getattr(module, "stack", None)
    if not cls:
        raise ImportError("Could not import {path}")
    return cls


def import_settings_from_string(path):
    (module, cls) = import_from_string(path)
    if cls is None:
        cls = getattr(module, "settings", None)
    if not cls:
        raise ImportError("Could not import {path}")
    return cls


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


main = typer.Typer(no_args_is_help=True)
settings = typer.Typer(no_args_is_help=True)
backend = typer.Typer(no_args_is_help=True)
main.add_typer(settings, name="settings")
main.add_typer(backend, name="backend")

app_arg = typer.Argument(
    help="Short unique application ID string. The same for all environments (eg. mywebapp)",
)

env_arg = typer.Argument(
    help="Environment instance of application. A namespace for all resources (eg. dev,test,prod)",
)

stacks_arg = typer.Argument(
    min=1, help="Python class path string of a CDKTF stack class"
)

setting_model_option = typer.Option(
    help="Python class path string to an AwsSettings model"
)


@main.command()
def run(
    app: str = app_arg,
    environment: str = env_arg,
    stacks: List[str] = stacks_arg,
    settings_model: Annotated[Optional[List[str]], settings_model_option] = [],
):
    print("Running cdktf app", app, environment, stacks, settings_model)


@settings.command()
def init(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_arg],
    settings_model: Annotated[Optional[str], settings_model_option] = None,
):
    print("Settings init", app, environment, settings_model)


@settings.command()
def show(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_arg],
    settings_model: Annotated[Optional[str], settings_model_option] = None,
):
    print("Settings show", app, environment, settings_model)
    show_settings(settings_model, app, environment)


@settings.command()
def delete(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_arg],
    settings_model: Annotated[Optional[str], settings_model_option] = None,
):
    print("Settings delete", app, environment, settings_model)


@backend.command()
def create(app: Annotated[str, app_arg]):
    from .stacks import AwsS3StateStack

    s3_bucket_name = AwsS3StateStack.format_s3_bucket_name(app)
    dynamodb_table_name = AwsS3StateStack.format_dynamodb_table_name(app)
    created, existing = ensure_backend_resources(s3_bucket_name, dynamodb_table_name)
    created = ", ".join([str(r) for r in created])
    existing = ", ".join([str(r) for r in existing])
    if created:
        print(f"Created resources: {created}")
    else:
        print("No resources needed creation")
    if existing:
        print(f"Resources already present: {existing}")
