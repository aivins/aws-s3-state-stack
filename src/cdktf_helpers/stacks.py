import re

import boto3
from cdktf import TerraformStack
from cdktf_cdktf_provider_aws.provider import AwsProvider
from constructs import Construct

from .backends import AutoS3Backend
from .settings.aws import AwsAppSettings
from .utils import unique_name


class AwsS3StateStack(TerraformStack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        s3_bucket_name=None,
        dynamodb_table_name=None,
        create_state_resources=False,
    ):
        super().__init__(scope, id)
        self._s3_bucket_name = s3_bucket_name
        self._dynamodb_table_name = dynamodb_table_name
        self._create_state_resources = create_state_resources

        # Hash a reasonably unique name for use as a bucket and dynamodb name for TF state
        self.unique_name = unique_name(self.settings.app)

        # Initialise the provider and the backend, which may create
        # resources to store TF state
        self.boto3_session = boto3.Session()
        self.register_provider()
        self.register_backend()

        # Call build, which is stacks should add their resources
        self.build()

    @property
    def s3_bucket_name(self):
        return self._s3_bucket_name or "{}-tfstate".format(
            re.sub(r"[\s_-]+", "-", self.unique_name)
        )

    @s3_bucket_name.setter
    def s3_bucket_name(self, value):
        self._s3_bucket_name = value

    @property
    def dynamodb_table_name(self):
        return self._dynamodb_table_name or "{}Tfstate".format(
            re.sub(r"[\s_-]+", " ", self.unique_name).title().replace(" ", "")
        )

    @dynamodb_table_name.setter
    def dynamodb_table_name(self, value):
        self._dynamodb_table_name = value

    @property
    def s3_key(self):
        return self.settings.environment

    @property
    def settings(self):
        if hasattr(self.node.root, "settings"):
            return self.node.root.settings
        else:
            # This is missing in tests
            return AwsAppSettings(app="app", environment="dev")

    def build(self):
        pass

    def register_provider(self):
        AwsProvider(self, "AWS", region=self.boto3_session.region_name)

    def register_backend(self):
        key = f"{self.s3_key}.tfstate"
        AutoS3Backend(
            self,
            bucket=self.s3_bucket_name,
            dynamodb_table=self.dynamodb_table_name,
            key=key,
            region=self.boto3_session.region_name,
            create_state_resources=self._create_state_resources,
        )
