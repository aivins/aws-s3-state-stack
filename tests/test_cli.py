import inspect
import os
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
    def _workdir(input=[], **overrides):
        if input:
            input = "\n".join(input) + "\n"
            monkeypatch.setattr("builtins.input", lambda _: input)
            # monkeypatch.setattr("sys.stdin", StringIO(input))
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

                yield tmp_path, settings

    return _workdir


arguments = ("testapp", "--environment", "dev", "--stack", "cli.Stack")


# def test_show_settings(workdir):
#     with workdir(input=["y"]):
#         result = runner.invoke(main, ["settings", "show", *arguments])
#         assert result.exit_code == 0


def test_delete_settings(workdir, capsys):
    with workdir(input=["y", "y"]) as (path, settings):
        delete_settings("testapp", "dev", type(settings))
        # captured = capsys.readouterr()


# def test_delete_settings_cli(workdir):
#     with workdir():
#         result = runner.invoke(
#             main,
#             ["settings", "delete", *arguments],
#             input="y\ny\n",
#         )
#         assert result.exit_code == 0
#         assert "Deleted 4 of 4 parameters" in result.stdout
