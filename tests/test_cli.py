import inspect
import json
import os
import re
import shutil
import sys
from contextlib import chdir, contextmanager
from functools import partial
from io import StringIO
from pathlib import Path
from typing import List

import pytest
from moto import mock_aws
from typer.testing import CliRunner

from cdktf_helpers.cli import main


@pytest.fixture()
def workdir(tmp_path):
    @contextmanager
    def _workdir(create_settings=True, **overrides):
        with mock_aws():
            source_dir = Path(__file__).parent
            with chdir(tmp_path):
                for source_file in ["cli.py", "cdktf.json"]:
                    shutil.copy(source_dir / source_file, tmp_path)

                if "" not in sys.path:
                    sys.path.insert(0, "")
                from cli import Settings

                settings = None
                if create_settings:
                    settings = Settings(app="testapp", environment="dev", **overrides)
                    settings.save()

                os.environ["COLUMNS"] = "1000"

                yield (tmp_path, Settings, settings)

    return _workdir


arguments = ("--environment", "dev")


def get_runner():
    runner = CliRunner()
    invoke = partial(runner.invoke, main, catch_exceptions=False)
    return invoke


def test_init_settings(workdir):
    input = "\n".join(["", "", "red", '["horse", "battery"]', "hello"]) + "\n"

    with workdir(create_settings=False) as (_, settings_model, _):
        invoke = get_runner()
        result = invoke(["settings", "init", *arguments], input=input)
        assert result.exit_code == 0

        data = settings_model.fetch_settings("testapp", "dev")

    assert "vpc" in data

    assert "colour" in data
    assert data["colour"] == "red"

    assert "animals" in data
    assert len(data["animals"]) == 2
    assert "horse" in data["animals"]

    assert "comment" in data
    assert data["comment"] == "hello"

    assert "comment_upper" in data
    assert data["comment_upper"] == "HELLO"


def test_show_settings(workdir):
    with workdir():
        invoke = get_runner()
        result = invoke(["settings", "show", *arguments])
        data = parse_show_output(result.stdout)
        assert data["vpc"]["value"].startswith("vpc-")


def test_delete_settings(workdir):
    with workdir():
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["settings", "delete", *arguments],
            input="y\ny\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "Deleted 8 of 8 parameters" in result.stdout


def parse_show_output(output):
    def split(line):
        return re.split(
            f"\s*{line[0]}\s*",
            line,
        )[1:-1]

    lines = output.split("\n")
    assert lines[0] == "Current settings for testapp/dev"
    header = set(split(lines[2]))
    assert header == {"Setting", "Description", "Value", "Required"}
    rows = [line for i, line in enumerate(lines[3:-2]) if not re.match(r"^[├╞]", line)]
    data = {}
    for row in rows:
        cols = split(row)
        key = cols[0]
        value = cols[2]
        match = re.search(r" \((.+)\)", value)
        origin = "user"
        if match:
            value = value[: -len(match.group(0))]
            origin = match.group(1)
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            pass
        data[key] = {"value": value, "origin": origin}
    return data
