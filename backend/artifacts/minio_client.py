import os
import boto3
from botocore.exceptions import ClientError
import logging

logger = logging.getLogger(__name__)

MINIO_URL = os.getenv("MINIO_URL", "http://localhost:9000")
# Inside docker compose, MINIO_URL is http://minio:9000. For local testing, we fallback to localhost.
MINIO_URL_RESOLVED = "http://localhost:9000" if "localhost" in MINIO_URL else MINIO_URL

s3_client = boto3.client(
    "s3",
    endpoint_url=MINIO_URL_RESOLVED,
    aws_access_key_id=os.getenv("MINIO_ROOT_USER", "admin"),
    aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD", "password123"),
    region_name="us-east-1"
)

def ensure_bucket(bucket_name: str):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            logger.error("Error ensuring bucket %s: %s", bucket_name, e)

def upload_file(bucket_name: str, object_name: str, file_path: str):
    ensure_bucket(bucket_name)
    s3_client.upload_file(file_path, bucket_name, object_name)

def download_file(bucket_name: str, object_name: str, file_path: str):
    s3_client.download_file(bucket_name, object_name, file_path)

def upload_bytes(bucket_name: str, object_name: str, data: bytes):
    ensure_bucket(bucket_name)
    s3_client.put_object(Bucket=bucket_name, Key=object_name, Body=data)

def get_bytes(bucket_name: str, object_name: str) -> bytes:
    response = s3_client.get_object(Bucket=bucket_name, Key=object_name)
    return response['Body'].read()
