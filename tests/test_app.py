from moto import mock_aws

from cdktf_helpers.apps import AwsApp
from cdktf_helpers.settings import (
    AwsAppSettings,
    SubnetsSetting,
    VpcSetting,
)


def test_aws_app_settings():
    with mock_aws():

        class Settings(AwsAppSettings):
            vpc_id: VpcSetting = VpcSetting()
            subnets: SubnetsSetting = SubnetsSetting()

        settings = Settings("myapp", "dev")
        app = AwsApp(settings)
        context = app.node.get_all_context()["settings"]
        assert context["vpc_id"]["value"].startswith("vpc-")
        assert all(value.startswith("subnet-") for value in context["subnets"]["value"])
