import json
from functools import cache

import boto3


@cache
def boto3_session():
    return boto3.Session()


def ensure_backend_resources(s3_bucket_name, dynamodb_table_name):
    assert s3_bucket_name
    assert dynamodb_table_name
    session = boto3_session()
    s3 = session.resource("s3")
    dynamodb = session.resource("dynamodb")
    created = []
    existing = []
    for bucket in s3.buckets.all():
        if bucket.name == s3_bucket_name:
            existing.append(bucket)
            break
    else:
        bucket = s3.create_bucket(
            Bucket=s3_bucket_name,
            CreateBucketConfiguration={"LocationConstraint": session.region_name},
        )
        created.append(bucket)
    for table in dynamodb.tables.all():
        if table.name == dynamodb_table_name:
            existing.append(table)
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
        created.append(table)
    return (created, existing)


def tags(obj):
    return {t["Key"]: t["Value"] for t in obj.resource.tags}
