import inspect
import json
import os
import re
import shutil
import sys
from contextlib import chdir, contextmanager
from io import StringIO
from pathlib import Path
from typing import List

import pytest
from moto import mock_aws
from typer.testing import CliRunner

from cdktf_helpers.cli import main

runner = CliRunner()


@pytest.fixture()
def workdir(tmp_path):
    @contextmanager
    def _workdir(**overrides):
        with mock_aws():
            source_dir = Path(__file__).parent
            with chdir(tmp_path):
                for source_file in ["cli.py", "cdktf.json"]:
                    shutil.copy(source_dir / source_file, tmp_path)

                if "" not in sys.path:
                    sys.path.insert(0, "")
                from cli import Settings

                settings = Settings(app="testapp", environment="dev", **overrides)
                settings.save()

                os.environ["COLUMNS"] = "1000"

                yield tmp_path, settings

    return _workdir


arguments = ("testapp", "--environment", "dev", "--stack", "cli.Stack")


def test_init_settings(workdir):
    input = "\n".join(["", "red", '["horse", "battery"]', "hello"]) + "\n"

    with workdir():
        result = runner.invoke(
            main, ["settings", "init", *arguments], input=input, catch_exceptions=False
        )
        assert result.exit_code == 0
        result = runner.invoke(main, ["settings", "show", *arguments])
        data = parse_show_output(result.stdout)

    # Should have found a value and its marked as default
    assert data["vpc"]["value"]
    assert data["vpc"]["origin"] == "default"

    # Strings should be read and marked user input
    assert data["colour"]["value"] == "red"
    assert data["colour"]["origin"] == "user"

    # List input should be correct length and user input
    assert len(data["animals"]["value"]) == 2
    assert "horse" in data["animals"]["value"]
    assert data["animals"]["origin"] == "user"

    # String input with a user input origin
    assert data["comment"]["value"] == "hello"
    assert data["comment"]["origin"] == "user"

    # Computed fields should be marked as such
    assert data["comment_upper"]["value"] == "HELLO"
    assert data["comment_upper"]["origin"] == "computed"


def test_show_settings(workdir):
    with workdir():
        result = runner.invoke(main, ["settings", "show", *arguments])
        data = parse_show_output(result.stdout)
        assert data["vpc"]["value"].startswith("vpc-")


def test_delete_settings(workdir):
    with workdir():
        result = runner.invoke(
            main,
            ["settings", "delete", *arguments],
            input="y\ny\n",
        )
        assert result.exit_code == 0
        assert "Deleted 5 of 5 parameters" in result.stdout


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
        value = json.loads(value)
        data[key] = {"value": value, "origin": origin}
    return data
