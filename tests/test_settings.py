import boto3
import pytest
from moto import mock_aws

from aws_s3_state_stack.settings import AwsAppSettings, Settings

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
        print(key, value)
        ssm.put_parameter(Type="String", Name=key, Value=value)
    yield AwsAppSettings(TEST_APP, TEST_ENV)


def test_aws_namespace(settings):
    assert settings.namespace == f"/{TEST_APP}/{TEST_ENV}"


def test_fetch_all_settings(settings):
    all_settings = settings.get_all()
    assert len(all_settings) == 3
    assert all_settings["foo"].value == "valueforfoo"
    assert str(all_settings["foo"]) == "valueforfoo"


def test_get_setting(settings):
    assert settings.get("bar").value == "true"
    assert str(settings.get("bar")) == "true"


def test_set_setting(settings):
    settings.set("hello", "there", "Just some setting")
    setting = settings.get("hello")
    setting.value == "there"
    setting.description == "Just some setting"


def test_set_bad_key(settings):
    with pytest.raises(Exception, match="Cannot set an empty key"):
        settings.set("", "blah")


def test_save_settings(settings, ssm):
    settings.set("new_key", "new_value")
    settings.set("new_key1", "new_value2")
    settings.save()
    response = ssm.get_parameters_by_path(Path=settings.namespace, Recursive=True)
    params = response["Parameters"]

    def present(key):
        return any(x["Name"] == settings.full_key(key) for x in params)

    assert present("foo")
    assert present("new_key")
    assert present("new_key1")

def test_typed_settings():
    class
