"""Cloudflare R2（S3 兼容）实现。public_url 走 R2_PUBLIC_BASE_URL。"""

from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.services.storage.base import ObjectStorage


class R2ObjectStorage(ObjectStorage):
    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        public_base_url: str,
    ):
        self._bucket = bucket
        self._base = public_base_url.rstrip("/")
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            # 有界超时+重试：R2 抖动/不可达时最多阻塞约 30s，而非无限挂起拖垮请求
            config=Config(
                signature_version="s3v4",
                connect_timeout=5,
                read_timeout=15,
                retries={"max_attempts": 2},
            ),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._s3.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
        )

    def get(self, key: str) -> Optional[bytes]:
        try:
            return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            # 只把"对象不存在"当 False；权限/网络等错误抛出，避免误配被当成空存储
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)

    def public_url(self, key: str) -> str:
        return f"{self._base}/{key}"
