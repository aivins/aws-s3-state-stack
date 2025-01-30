#!/usr/bin/env python

import os
import sys
import time

import boto3
from cdktf import Resource, TerraformStack
from cdktf_cdktf_provider_aws.provider import AwsProvider
from constructs import Construct

from .backends import AutoS3Backend


class AwsS3StateStack(TerraformStack):
    def __init__(
        self, scope: Construct, id: str, s3_bucket_name=None, dynamodb_table_name=None
    ):
        super().__init__(scope, id)
        self.namespace = self.node.try_get_context("namespace") or "app"
        self.boto3_session = boto3.Session()
        self._s3_bucket_name = s3_bucket_name
        self._dynamodb_table_name = dynamodb_table_name
        self.register_provider()
        self.register_backend()
        self.build()

    @property
    def s3_bucket_name(self):
        return self._s3_bucket_name or "{}-tfstate".format(
            self.namespace.replace("_", "-")
        )

    @s3_bucket_name.setter
    def s3_bucket_name(self, value):
        self._s3_bucket_name = value

    @property
    def dynamodb_table_name(self):
        return self._dynamodb_table_name or "{}Tfstate".format(
            self.namespace.title().replace(" ", "")
        )

    @dynamodb_table_name.setter
    def dynamodb_table_name(self, value):
        self._dynamodb_table_name = value

    @property
    def s3_key(self):
        if "TF_WORKSPACE" not in os.environ:
            print(
                "AwsS3StateStack: TF_WORKSPACE environment variable must be set",
                file=sys.stderr,
            )
            sys.exit(1)
        return os.environ["TF_WORKSPACE"]

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
        )
