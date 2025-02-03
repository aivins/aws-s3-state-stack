#!/usr/bin/env python


from cdktf import App, TerraformOutput
from cdktf_cdktf_provider_aws.instance import Instance

from cdktf_helpers.settings.aws import AwsAppSettings
from cdktf_helpers.stacks import AwsS3StateStack


class MyStack(AwsS3StateStack[AwsAppSettings]):
    def build(self):
        instance = Instance(
            self,
            "compute",
            ami="ami-0d11f9bfe33cfbe8b",
            instance_type="t2.micro",
        )

        TerraformOutput(
            self,
            "public_ip",
            value=instance.public_ip,
        )


if __name__ == "__main__":
    app = App()
    stack = MyStack(app, "test_stack")
    app.synth()
