import argparse

import boto3
from cdktf import S3Backend


class AutoS3Backend(S3Backend):
    def __init__(
        self, scope, bucket, dynamodb_table, create_state_resources=False, **kwargs
    ):
        from .settings.aws import ensure_backend_resources

        if create_state_resources:
            ensure_backend_resources(bucket, dynamodb_table)
        super().__init__(scope, bucket=bucket, dynamodb_table=dynamodb_table, **kwargs)
