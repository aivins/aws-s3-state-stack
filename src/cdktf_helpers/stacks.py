import re
from typing import Generic, get_args, get_origin

import boto3
from cdktf import TerraformStack
from cdktf_cdktf_provider_aws.provider import AwsProvider
from constructs import Construct

from .backends import AutoS3Backend
from .settings.aws import AwsAppSettings, AwsAppSettingsType
from .settings.base import AppSettingsType
from .utils import unique_name


class AwsStack(TerraformStack, Generic[AppSettingsType]):
    def __init__(self, scope: Construct, id: str, settings: AppSettingsType):
        super().__init__(scope, id)
        self.settings = settings

    def build(self):
        pass


class AwsS3StateStack(AwsStack[AwsAppSettings], Generic[AwsAppSettingsType]):
    def __init__(
        self,
        scope: Construct,
        id: str,
        settings: AwsAppSettingsType,
        s3_bucket_name: str = None,
        dynamodb_table_name: str = None,
        create_state_resources=False,
    ):
        super().__init__(scope, id, settings)
        self._s3_bucket_name = s3_bucket_name
        self._dynamodb_table_name = dynamodb_table_name
        self._create_state_resources = create_state_resources

        # Initialise the provider and the backend, which may create
        # resources to store TF state
        self.boto3_session = boto3.Session()
        self.register_provider()
        self.register_backend()

        # Call build, which is stacks should add their resources
        self.build()

    @classmethod
    def get_settings_model(cls):
        for base in cls.__orig_bases__:
            origin = get_origin(base)
            if issubclass(origin, AwsStack):
                return get_args(base)[0]

    @classmethod
    def format_s3_bucket_name(cls, app):
        name = unique_name(app)
        return "{}-tfstate".format(re.sub(r"[\s_-]+", "-", name))

    @classmethod
    def format_dynamodb_table_name(cls, app):
        name = unique_name(app)
        return "{}Tfstate".format(
            re.sub(r"[\s_-]+", " ", name).title().replace(" ", "")
        )

    @property
    def s3_bucket_name(self):
        return self._s3_bucket_name or self.format_s3_bucket_name(self.settings.app)

    @s3_bucket_name.setter
    def s3_bucket_name(self, value):
        self._s3_bucket_name = value

    @property
    def dynamodb_table_name(self):
        return self._dynamodb_table_name or self.format_dynamodb_table_name(
            self.settings.app
        )

    @dynamodb_table_name.setter
    def dynamodb_table_name(self, value):
        self._dynamodb_table_name = value

    @property
    def s3_key(self):
        return self.settings.environment

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
