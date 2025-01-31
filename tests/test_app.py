from moto import mock_aws

from aws_s3_state_stack.apps import AwsApp
from aws_s3_state_stack.settings import AwsAppSettings, SubnetsSetting, VpcSetting


def test_aws_app_settings():
    with mock_aws():

        class Settings(AwsAppSettings):
            vpc_id: VpcSetting
            subnets: SubnetsSetting

        settings = Settings("myapp", "dev")
        app = AwsApp(settings)
