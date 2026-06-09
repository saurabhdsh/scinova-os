"""Shared AWS Bedrock runtime client for embeddings and LLM."""

from __future__ import annotations

import os

from app.config import settings


def aws_region() -> str:
    return (
        settings.aws_region
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or "us-east-1"
    )


def bedrock_credentials_available() -> bool:
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        return True
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        return True
    if os.environ.get("AWS_PROFILE"):
        return True
    if os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"):
        return True
    try:
        import boto3

        session = boto3.Session(region_name=aws_region())
        return session.get_credentials() is not None
    except Exception:
        return False


def get_bedrock_runtime_client():
    import boto3

    kwargs: dict = {"region_name": aws_region()}
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
    return boto3.client("bedrock-runtime", **kwargs)
