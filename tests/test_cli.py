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

from cdktf_helpers.cli import delete_settings, main

runner = CliRunner()


@pytest.fixture()
def workdir(tmp_path, monkeypatch):
    @contextmanager
    def _workdir(**overrides):
        # if input:
        #     input = "\n".join(input) + "\n"
        #     monkeypatch.setattr("builtins.input", lambda _: input)
        #     # monkeypatch.setattr("sys.stdin", StringIO(input))
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

                # _get_terminal_size = shutil.get_terminal_size

                # def get_terminal_size(*args, **kwargs):
                #     terminal_size = _get_terminal_size(*args, **kwargs)
                #     terminal_size.columns = 1000
                #     return terminal_size

                # monkeypatch.setattr("shutil.get_terminal_size", get_terminal_size)

                yield tmp_path, settings

    return _workdir


arguments = ("testapp", "--environment", "dev", "--stack", "cli.Stack")


def test_init_settings(workdir):
    input = "\n".join(["vpc-12345abcd", "", '["horse"]', "hello"]) + "\n"

    with workdir():
        result = runner.invoke(
            main, ["settings", "init", *arguments], input=input, catch_exceptions=False
        )
        assert result.exit_code == 0
        result = runner.invoke(main, ["settings", "show", *arguments])
        data = parse_show_output(result.stdout)
    assert "horse" in data["animals"]


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
        assert "Deleted 4 of 4 parameters" in result.stdout


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
