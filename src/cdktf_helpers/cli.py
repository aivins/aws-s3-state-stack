import importlib
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Annotated, List, Optional, get_origin

import typer
from botocore.exceptions import UnauthorizedSSOTokenError
from cdktf import App
from pydantic import TypeAdapter, ValidationError
from pydantic_core import PydanticUndefined
from rich import print
from tabulate import tabulate

from cdktf_helpers.settings.aws.utils import (
    boto3_session,
    fetch_settings,
    get_all_settings,
)

from .settings.aws import ensure_backend_resources


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
    add_completion=False,
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

dry_run_option = typer.Option(help="Simulate command without apply changes")


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


def synth_cdktf_app(
    app_name, environment, *stack_classes, create_state_resources=False
):
    app = App()

    for stack_class in stack_classes:
        settings_model = stack_class.get_settings_model()
        settings = validate_settings(settings_model, app_name, environment)

        stack_class(
            app,
            stack_class.__name__,
            settings,
            create_state_resources=create_state_resources,
        )
        print(f"Added {stack_class.__name__} to {app_name}/{environment}")

    app.synth()


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
    "output": (cdktf_multi_stack, "Prints the output of stacks"),
    "debug": (
        cdtkf_simple,
        "Get debug information about the current project and environment",
    ),
}

for command, (create_command, help) in cdktf_commands.items():
    create_command(main, command, help)


def initialise_settings(app, environment, settings_model, dry_run=False):
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

        def field_is(f, t):
            result = False
            if isinstance(f.annotation, type):
                result = issubclass(f.annotation, t)
            else:
                result = get_origin(f.annotation) is t
            return result

        str_input = field_is(field, str)
        list_input = field_is(field, list)

        value = None
        default_msg = f" [{current_value_json}]" if current_value is not None else ""
        list_msg = " as JSON list" if list_input else ""

        # Prompt interactively for new value for each key, with defaults
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
                    elif str_input:
                        value = validator.validate_strings(value)
                    else:
                        # an object is expected, create it from a resource id
                        value = field.annotation(id=value)
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


@settings.command()
def init(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_option] = None,
    stack: Annotated[str, stack_arg] = default_stack,
    dry_run: Annotated[bool, dry_run_option] = False,
):
    initialise_settings(app, environment, stack.get_settings_model(), dry_run)


def show_settings(app, environment, settings_model):
    """Pretty print the current paramstore settings for an app/environment"""

    terminal_width = shutil.get_terminal_size().columns
    col_percent_widths = (20, 35, 35, 10)
    col_widths = [
        int(col_width * terminal_width / 100) for col_width in col_percent_widths
    ]

    settings_data = get_all_settings(
        app,
        environment,
        settings_model,
    )

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


@settings.command()
def show(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_option] = None,
    stack: Annotated[str, stack_arg] = default_stack,
):
    show_settings(app, environment, stack.get_settings_model())


def delete_settings(app, environment, settings_model, dry_run=False):
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


@settings.command()
def delete(
    app: Annotated[str, app_arg],
    environment: Annotated[str, env_option] = None,
    stack: Annotated[str, stack_arg] = default_stack,
    dry_run: Annotated[bool, dry_run_option] = False,
):
    delete_settings(app, environment, stack.get_settings_model(), dry_run)


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
        main()
    except UnauthorizedSSOTokenError:
        print(
            "Looks like you don't have a valid AWS SSO session. "
            "Start one with `aws sso login` or manually configure your "
            "environment before trying again."
        )
        sys.exit(1)


def validate_settings(settings_model, app_name, environment):
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
    return settings
