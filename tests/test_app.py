from typing import List

from moto import mock_aws

from cdktf_helpers.apps import AwsApp
from cdktf_helpers.settings import AwsAppSettings, SubnetsField, VpcField


def test_aws_app_settings():
    with mock_aws():

        class Settings(AwsAppSettings):
            vpc_id: str = VpcField()
            subnets: List[str] = SubnetsField()

        settings = Settings(app="myapp", environment="dev")
        app = AwsApp(settings)

        assert app.settings.vpc_id.startswith("vpc-")
        assert all(value.startswith("subnet-") for value in app.settings.subnets)
