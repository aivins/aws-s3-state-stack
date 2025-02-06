import json
from typing import List

import boto3
import pytest
from moto import mock_aws
from pydantic import BaseModel, Field

from cdktf_helpers.settings.aws import (
    AwsAppSettings,
    AwsResources,
    Subnet,
    SubnetsField,
    Vpc,
    VpcField,
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
            Type="String",
            Name=key,
            Value=json.dumps(value),
            Description="Some description",
        )

    class TestSettings(AwsAppSettings):
        foo: str = Field(description="Just foo")
        bar: str = Field(description="And bar")
        other: str
        something_interesting: str = "not really"
        something_else: str = "equally boring"

    yield TestSettings(app=TEST_APP, environment=TEST_ENV)


def test_namespace(settings):
    assert settings.namespace == f"/{TEST_APP}/{TEST_ENV}/"


def test_settings(settings):
    assert settings.foo == "valueforfoo"
    assert settings.get_description("foo") == "Just foo"


# def test_resource_type_coercion():
#     class TestSettings(AwsAppSettings):
#         vpc: Vpc = VpcField()
#         subnets: AwsResources[Subnet] = SubnetsField()
#         required_field: str

#     with mock_aws():
#         # input_data = {
#         #     "vpc": "vpc-abcd1234",
#         #     "subnets": ["subnet-a123", "subnet-b456", "subnet-c789"],
#         # }
#         input_data = {"required_field": "sausages"}
#         settings_dict = TestSettings.model_dict("app", "dev", **input_data)
#         settings = TestSettings.model_validate(settings_dict)
#         pass


def test_as_dict(settings):
    as_dict = settings.as_dict()
    assert isinstance(as_dict, dict)
    assert len(as_dict) == 5


def test_as_dict_prefix(settings):
    as_dict = settings.as_dict(prefix="something_")
    assert len(as_dict) == 2
    assert "something_interesting" in as_dict
    assert "something_else" in as_dict


def test_as_env(settings):
    as_dict = settings.as_env(prefix="something_")
    assert as_dict == [
        {"name": "SOMETHING_INTERESTING", "value": "not really"},
        {"name": "SOMETHING_ELSE", "value": "equally boring"},
    ]


def test_save_settings(ssm):
    with mock_aws():

        class TestSettings(AwsAppSettings):
            blah: str

        settings = TestSettings(
            app="anotherapp",
            environment=TEST_ENV,
            blah="bloh",
        )

        settings.save()

        response = ssm.get_parameters_by_path(Path=settings.namespace, Recursive=True)
        params = response["Parameters"]

        def present(key):
            return any(x["Name"].endswith(f"/{key}") for x in params)

        assert present("blah")


def test_vpc_setting():
    with mock_aws():

        class Settings(AwsAppSettings):
            vpc: Vpc = VpcField()

        settings = Settings(app="testapp", environment="dev")

        assert settings.vpc.id.startswith("vpc-")


def test_subnets_setting():
    with mock_aws():

        class Settings(AwsAppSettings):
            vpc: Vpc = VpcField()
            subnets: AwsResources[Subnet] = SubnetsField()

        settings = Settings(app="testapp", environment="dev")
        assert all(value.id.startswith("subnet-") for value in settings.subnets)
