"""Cloudflare R2 upload helpers (S3-compatible API)."""
import logging
import secrets
import time
from typing import Callable

import boto3
from botocore.exceptions import ClientError

import config

logger = logging.getLogger("bili2vrchat")

_RANDOM_CHARS = "ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678"
_client = None


def random_object_key(length: int = 6) -> str:
    return "".join(secrets.choice(_RANDOM_CHARS) for _ in range(length))


def get_client():
    global _client
    if _client is not None:
        return _client

    missing = [
        name for name, value in (
            ("CF_ACCOUNT_ID", config.CF_ACCOUNT_ID),
            ("R2_ACCESS_KEY_ID", config.R2_ACCESS_KEY_ID),
            ("R2_SECRET_ACCESS_KEY", config.R2_SECRET_ACCESS_KEY),
            ("R2_BUCKET_NAME", config.R2_BUCKET_NAME),
        )
        if not config.is_set(value)
    ]
    if missing:
        raise RuntimeError(
            "請設定 R2 環境變數：" + "、".join(missing)
        )

    _client = boto3.client(
        "s3",
        endpoint_url=f"https://{config.CF_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=config.R2_ACCESS_KEY_ID,
        aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )
    return _client


def resolve_object_key(key_phrase: str) -> tuple[str, str | None]:
    """Return (object_key, error_message). error_message is set on conflict or reserved path."""
    key = key_phrase.strip() if key_phrase else ""
    if not key:
        return f"f_{random_object_key()}", None

    client = get_client()
    try:
        client.head_object(Bucket=config.R2_BUCKET_NAME, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey", "NotFound"):
            return key, None
        raise

    return "", f"路徑「{key}」已有檔案，請換一個名稱，或至 R2 手動刪除後重試"


def expires_value_for_ttl(ttl_seconds: int) -> str:
    if ttl_seconds > 0:
        return str(int(time.time() * 1000) + ttl_seconds * 1000)
    return "0"


def ttl_notice(ttl_seconds: int) -> str:
    notices = {
        3600: "1 小時後自動刪除",
        86400: "1 天後自動刪除",
        604800: "7 天後自動刪除",
        2592000: "30 天後自動刪除",
        0: "永久保存（不會自動刪除）",
    }
    return notices.get(ttl_seconds, f"{ttl_seconds} 秒後自動刪除")


def purge_expired_objects() -> tuple[int, int]:
    """Scan bucket and delete objects past expires metadata. Returns (scanned, deleted)."""
    client = get_client()
    now_ms = int(time.time() * 1000)
    scanned = 0
    deleted = 0

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=config.R2_BUCKET_NAME):
        for item in page.get("Contents", []):
            key = item["Key"]
            scanned += 1
            try:
                head = client.head_object(Bucket=config.R2_BUCKET_NAME, Key=key)
            except ClientError:
                continue

            expires = head.get("Metadata", {}).get("expires", "")
            if not expires or expires == "0":
                continue

            try:
                expire_ts = int(expires)
            except ValueError:
                continue

            if now_ms > expire_ts:
                client.delete_object(Bucket=config.R2_BUCKET_NAME, Key=key)
                deleted += 1
                logger.info("r2 expired delete: %s", key)

    return scanned, deleted


def upload_file(
    local_path: str,
    object_key: str,
    filename_encoded: str,
    expires_value: str,
    on_progress: Callable[[int, int], None] | None = None,
    cancel_event=None,
) -> None:
    client = get_client()
    file_size = 0
    with open(local_path, "rb") as probe:
        probe.seek(0, 2)
        file_size = probe.tell()

    uploaded = 0
    last_pct = -1

    def callback(bytes_amount: int) -> None:
        nonlocal uploaded, last_pct
        if cancel_event and cancel_event.is_set():
            raise InterruptedError("cancelled")
        uploaded += bytes_amount
        if on_progress and file_size > 0:
            pct = int(uploaded / file_size * 100)
            if pct != last_pct:
                last_pct = pct
                on_progress(uploaded, file_size)

    with open(local_path, "rb") as file_obj:
        client.upload_fileobj(
            file_obj,
            config.R2_BUCKET_NAME,
            object_key,
            ExtraArgs={
                "ContentType": "video/mp4",
                "Metadata": {
                    "filename": filename_encoded,
                    "expires": expires_value,
                },
            },
            Callback=callback,
        )

    logger.info("r2 upload ok: key=%s bytes=%s", object_key, file_size)


def build_object_url(object_key: str) -> str:
    """Return public HTTP URL if R2_PUBLIC_BASE_URL is set, else r2://bucket/key."""
    if config.is_set(config.R2_PUBLIC_BASE_URL):
        return f"{config.R2_PUBLIC_BASE_URL}/{object_key}"
    return f"r2://{config.R2_BUCKET_NAME}/{object_key}"
