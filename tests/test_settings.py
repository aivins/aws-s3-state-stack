import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel

from aws_s3_state_stack.settings import AwsAppSettings, Setting

TEST_APP = "myapp"
TEST_ENV = "dev"
TEST_PARAMS = {
    f"/{TEST_APP}/{TEST_ENV}/foo": "valueforfoo",
    f"/{TEST_APP}/{TEST_ENV}/bar": "true",
    f"/{TEST_APP}/{TEST_ENV}/other": "10",
}


@pytest.fixture(scope="module")
def ssm():
    with mock_aws():
        session = boto3.Session()
        ssm = session.client("ssm")
        yield ssm


@pytest.fixture(scope="module")
def settings(ssm):
    for key, value in TEST_PARAMS.items():
        ssm.put_parameter(
            Type="String", Name=key, Value=value, Description="Some description"
        )

    class TestSettings(AwsAppSettings):
        foo: Setting
        bar: Setting
        other: Setting

    yield TestSettings(app=TEST_APP, environment=TEST_ENV)


def test_aws_namespace(settings):
    assert settings.namespace == f"/{TEST_APP}/{TEST_ENV}"


def test_settings(settings):
    assert settings.foo.value == "valueforfoo"
    assert settings.foo.description == "Some description"


def test_set_setting(settings):
    settings.set("foo", "there", "Just some setting")
    assert settings.foo.value == "there"
    assert settings.foo.description == "Just some setting"


def test_set_empty_key(settings):
    with pytest.raises(Exception, match="Cannot set an empty key"):
        settings.set("", "blah")


def test_set_invalid_key(settings):
    with pytest.raises(Exception, match="not a field"):
        settings.set("badkey", "blah")


def test_user_input(monkeypatch):
    inputs = iter(["valueforblah", "This is very blah"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    with mock_aws():

        class TestSettings(AwsAppSettings):
            blah: Setting

        settings = TestSettings("anotherapp", TEST_ENV)
        assert settings.blah.value == "valueforblah"
        assert settings.blah.description == "This is very blah"


def test_save_settings(ssm):
    with mock_aws():

        class TestSettings(AwsAppSettings):
            blah: Setting

        settings = TestSettings(
            "anotherapp", TEST_ENV, blah=Setting(key="blah", value="bloh")
        )

        settings.save()

        response = ssm.get_parameters_by_path(Path=settings.namespace, Recursive=True)
        params = response["Parameters"]

        def present(key):
            return any(x["Name"].endswith(f"/{key}") for x in params)

        assert present("blah")
