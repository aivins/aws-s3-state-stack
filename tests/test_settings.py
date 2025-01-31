import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel

from cdktf_helpers.settings import (
    AwsAppSettings,
    Setting,
    SubnetsSetting,
    VpcSetting,
)

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


@pytest.fixture(scope="module")
def vpc_and_subnets():
    with mock_aws():
        session = boto3.Session()
        ec2 = session.resource("ec2")
        vpc = ec2.create_vpc(CidrBlock="10.0.0.0/16")
        subnets = [vpc.create_subnet(CidrBlock=f"10.0.{i}.0/25") for i in range(3)]
        yield vpc, subnets


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


def test_save_settings(ssm):
    with mock_aws():

        class TestSettings(AwsAppSettings):
            blah: Setting

        settings = TestSettings(
            app="anotherapp",
            environment=TEST_ENV,
            blah=Setting(key="blah", value="bloh"),
        )

        settings.save()

        response = ssm.get_parameters_by_path(Path=settings.namespace, Recursive=True)
        params = response["Parameters"]

        def present(key):
            return any(x["Name"].endswith(f"/{key}") for x in params)

        assert present("blah")


def test_vpc_setting():
    with mock_aws():

        class Settings(BaseModel):
            vpc: VpcSetting = VpcSetting()

        settings = Settings()

        assert settings.vpc.value.startswith("vpc-")


def test_subnets_setting():
    with mock_aws():

        class Settings(BaseModel):
            vpc: VpcSetting = VpcSetting()
            subnets: SubnetsSetting = SubnetsSetting()

        settings = Settings()
        assert all(value.startswith("subnet-") for value in settings.subnets.value)
