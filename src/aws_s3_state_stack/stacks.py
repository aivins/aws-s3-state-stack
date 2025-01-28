#!/usr/bin/env python

import os

import boto3
from cdktf import S3Backend, TerraformStack
from cdktf_cdktf_provider_aws.provider import AwsProvider
from constructs import Construct


class AwsS3StateStack(TerraformStack):
    def __init__(
        self, scope: Construct, ns: str, s3_bucket_name=None, dynamodb_table_name=None
    ):
        super().__init__(scope, ns)
        self.boto3_session = boto3.Session()
        self.ns = ns
        self._s3_bucket_name = s3_bucket_name
        self._dynamodb_table_name = dynamodb_table_name
        self.ensure_backend_resources()
        self.register_provider()
        self.register_backend()
        self.build()

    @property
    def s3_bucket_name(self):
        return self._s3_bucket_name or "{}-tfstate".format(self.ns.replace("_", "-"))

    @s3_bucket_name.setter
    def s3_bucket_name(self, value):
        self._s3_bucket_name = value

    @property
    def dynamodb_table_name(self):
        return self._dynamodb_table_name or "{}Tfstate".format(
            self.ns.title().replace(" ", "")
        )

    @dynamodb_table_name.setter
    def dynamodb_table_name(self, value):
        self._dynamodb_table_name = value

    def build(self):
        pass

    def register_provider(self):
        AwsProvider(self, "AWS", region=self.boto3_session.region_name)

    def register_backend(self):
        key = f"{self.node.id}.tfstate"
        S3Backend(
            self,
            bucket=self.s3_bucket_name,
            dynamodb_table=self.dynamodb_table_name,
            key=key,
            region=self.boto3_session.region_name,
        )

    def ensure_backend_resources(self):
        s3 = self.boto3_session.resource("s3")
        dynamodb = self.boto3_session.resource("dynamodb")
        for bucket in s3.buckets.all():
            if bucket.name == self.s3_bucket_name:
                break
        else:
            bucket = s3.create_bucket(
                Bucket=self.s3_bucket_name,
                CreateBucketConfiguration={
                    "LocationConstraint": self.boto3_session.region_name
                },
            )
        for table in dynamodb.tables.all():
            if table.name == self.dynamodb_table_name:
                break
        else:
            table = dynamodb.create_table(
                TableName=self.dynamodb_table_name,
                KeySchema=[
                    {
                        "AttributeName": "LockID",
                        "KeyType": "HASH",
                    }
                ],
                AttributeDefinitions=[
                    {
                        "AttributeName": "LockID",
                        "AttributeType": "S",
                    }
                ],
                BillingMode="PAY_PER_REQUEST",
            )
