import argparse

import boto3
from cdktf import S3Backend


class AutoS3Backend(S3Backend):
    def __init__(
        self, scope, bucket, dynamodb_table, create_state_resources=False, **kwargs
    ):
        if create_state_resources:
            self.ensure_backend_resources(bucket, dynamodb_table)
        super().__init__(scope, bucket=bucket, dynamodb_table=dynamodb_table, **kwargs)

    @classmethod
    def ensure_backend_resources(cls, s3_bucket_name, dynamodb_table_name):
        assert s3_bucket_name
        assert dynamodb_table_name
        session = boto3.Session()
        s3 = session.resource("s3")
        dynamodb = session.resource("dynamodb")
        for bucket in s3.buckets.all():
            if bucket.name == s3_bucket_name:
                break
        else:
            bucket = s3.create_bucket(
                Bucket=s3_bucket_name,
                CreateBucketConfiguration={"LocationConstraint": session.region_name},
            )
        for table in dynamodb.tables.all():
            if table.name == dynamodb_table_name:
                break
        else:
            table = dynamodb.create_table(
                TableName=dynamodb_table_name,
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


def create_backend_resources():
    parser = argparse.ArgumentParser()
    parser.add_argument("s3_bucket_name", help="Name of S3 bucket to create")
    parser.add_argument("dynamodb_table_name", help="Name of DynamoDB table to create")
    options = parser.parse_args()
    AutoS3Backend.ensure_backend_resources(**vars(options))


if __name__ == "__main__":
    create_backend_resources()
