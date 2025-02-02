import functools
import importlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Any, Callable, List, Optional, TypeVar

import click
import typer
from botocore.exceptions import UnauthorizedSSOTokenError
from pydantic import BaseModel
from rich import print

from .settings.aws import (
    delete_settings,
    ensure_backend_resources,
    initialise_settings,
    show_settings,
    synth_cdktf_app,
)


def import_from_string(path):
    module_name, class_name = path.rsplit(".", 1)
    try:
        sys.path.insert(0, "")
        module = importlib.import_module(module_name)
        sys.path.pop(0)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as e:
        print(f"Could not import {path}: {e}")
        sys.exit(1)
    return cls


def import_from_strings(paths):
    classes = []
    for path in paths:
        classes.append(import_from_string(path))
    return classes


def to_path(cls):
    return f"{cls.__module__}.{cls.__qualname__}"


def to_paths(*classes):
    paths = []
    for cls in classes:
        paths.append(to_path(cls))
    return paths


main = typer.Typer(
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    help="Commands to work with CDKTF python apps",
)
settings = typer.Typer(no_args_is_help=True, help="Manage stored app settings")
backend = typer.Typer(no_args_is_help=True, help="Manage Terraform state backend")
run = typer.Typer(
    no_args_is_help=True,
    help="Wrapper commands that invoke cdktf with correct arguments",
)

main.add_typer(settings, name="settings")
main.add_typer(backend, name="backend")
main.add_typer(run, name="run")

app_arg = typer.Argument(
    help="Short unique application ID string. The same for all environments (eg. mywebapp)",
)


def env_option_validate(value):
    if not value:
        raise typer.BadParameter(
            "Must supply either --environment or set CDKTF_APP_ENVIRONMENT"
        )
    return value


env_option = typer.Option(
    callback=env_option_validate,
    envvar="CDKTF_APP_ENVIRONMENT",
    help="Environment instance of application. A namespace for all resources (eg. dev,test,prod)",
)

stacks_arg = typer.Option(
    min=1,
    help="Python class path strings of CDKTF stack classes",
    callback=import_from_strings,
)

stack_arg = typer.Option(
    help="Python class path string of CDKTF stack class",
    callback=import_from_string,
)


def get_stacks_from_config():
    config_file = Path("cdktf.json")
    if config_file.exists():
        with open(config_file.name, "r") as fh:
            config = json.load(fh)
        stacks = config.get("context", {}).get("stacks")
        if isinstance(stacks, list):
            return stacks
    return []


default_stacks = get_stacks_from_config() or ["main.Stack"]
default_stack = default_stacks[0]


@main.command(help="Synthesize app directly without invoking cdktf")
def synth(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_option] = None,
    stacks: Annotated[Optional[List[str]], stacks_arg] = default_stacks,
):
    stacks = stacks or default_stacks
    synth_cdktf_app(app, environment, *stacks)


def cdktf_multi_stack(parent, command, help):
    def wrapper(
        environment: Annotated[str, env_option] = None,
        stacks: Annotated[Optional[List[str]], stacks_arg] = default_stacks,
    ):
        os.environ["CDKTF_APP_ENVIRONMENT"] = environment
        stacks = to_paths(*stacks)
        subprocess.run(["cdktf", command, *stacks])

    return parent.command(name=command, help=help)(wrapper)


def cdktf_single_stack(parent, command, help):
    def wrapper(
        environment: Annotated[str, env_option] = None,
        stack: Annotated[str, stack_arg] = default_stack,
    ):
        os.environ["CDKTF_APP_ENVIRONMENT"] = environment
        stack = to_paths(stack)
        subprocess.run(["cdktf", command, stack])

    return parent.command(name=command, help=help)(wrapper)


def cdtkf_simple(parent, command, help):
    def wrapper():
        subprocess.run(["cdktf", command])

    return parent.command(name=command, help=help)(wrapper)


cdktf_commands = {
    "deploy": (cdktf_multi_stack, "Deploy the given stacks"),
    "destroy": (cdktf_multi_stack, "Destroy the given stacks"),
    "diff": (cdktf_single_stack, "Perform a diff (terraform plan) for the given stack"),
    "list": (cdtkf_simple, "List stacks in app"),
    "synth": (
        cdtkf_simple,
        "Synthesizes Terraform code for the given app in a directory",
    ),
    "output": (cdktf_multi_stack, "Prints the output of stacks"),
    "debug": (
        cdtkf_simple,
        "Get debug information about the current project and environment",
    ),
}

for command, (create_command, help) in cdktf_commands.items():
    create_command(main, command, help)

# cdktf_multi_stack(
#     main, "deploy", "Deploy the given stacks. Convenience shortcut for `run deploy`"
# )


@settings.command()
def init(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_option] = None,
    stack: Annotated[str, stack_arg] = default_stack,
):
    initialise_settings(app, environment, stack.get_settings_model())


@settings.command()
def show(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_option] = None,
    stack: Annotated[str, stack_arg] = default_stack,
):
    show_settings(app, environment, stack.get_settings_model())


@settings.command()
def delete(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_option] = None,
    stack: Annotated[str, stack_arg] = default_stack,
):
    delete_settings(app, environment, stack.get_settings_model())


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


def entrypoint():
    if not shutil.which("cdktf"):
        print(
            "cdktf program not found on path. This is needed to run the deploy command."
        )
    try:
        main(standalone_mode=False)
    except UnauthorizedSSOTokenError:
        print(
            "Looks like you don't have a valid AWS SSO session. "
            "Start one with `aws sso login` or manually configure your "
            "environment before trying again."
        )
        sys.exit(1)
