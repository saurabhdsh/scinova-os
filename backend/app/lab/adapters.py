"""Replaceable adapters. Local landing and lake are real file stores. ELN is an explicit simulation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.lab.errors import LabError


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass
class StoredObject:
    uri: str
    sha256: str
    byte_size: int
    mode: str
    external: bool
    simulation: bool


class LocalLandingZone:
    """Immutable filesystem landing zone. Used when no S3 bucket is configured."""

    mode = "local"
    simulation = False
    external = False

    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.lab_landing_dir)

    def put_immutable(self, filename: str, content: bytes) -> StoredObject:
        digest = sha256_bytes(content)
        safe_name = Path(filename).name or "instrument.dat"
        dest = self.root / digest[:2] / digest / safe_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            existing = dest.read_bytes()
            if sha256_bytes(existing) != digest:
                raise LabError(
                    "Landing object already exists with different bytes. Raw data is immutable.",
                    status_code=409,
                    code="raw_immutable",
                )
        else:
            dest.write_bytes(content)
        verified = dest.read_bytes()
        if sha256_bytes(verified) != digest:
            raise LabError("Checksum verification failed after write.", status_code=500, code="checksum_failed")
        return StoredObject(
            uri=str(dest),
            sha256=digest,
            byte_size=len(content),
            mode=self.mode,
            external=False,
            simulation=False,
        )

    def read(self, uri: str) -> bytes:
        return Path(uri).read_bytes()

    def verify(self, uri: str, digest: str) -> bool:
        return sha256_bytes(Path(uri).read_bytes()) == digest


class S3LandingZone:
    """AWS S3 landing zone. Selected only when lab_landing_bucket is set."""

    mode = "s3"
    simulation = False
    external = True

    def __init__(self, bucket: str):
        self.bucket = bucket

    def _client(self):
        import boto3

        return boto3.client("s3", region_name=settings.aws_region or None)

    def put_immutable(self, filename: str, content: bytes) -> StoredObject:
        digest = sha256_bytes(content)
        key = f"lab/landing/{digest[:2]}/{digest}/{Path(filename).name}"
        client = self._client()
        try:
            client.head_object(Bucket=self.bucket, Key=key)
        except Exception:
            client.put_object(Bucket=self.bucket, Key=key, Body=content, Metadata={"sha256": digest})
        remote = client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        if sha256_bytes(remote) != digest:
            raise LabError("S3 checksum verification failed.", status_code=500, code="checksum_failed")
        return StoredObject(
            uri=f"s3://{self.bucket}/{key}",
            sha256=digest,
            byte_size=len(content),
            mode=self.mode,
            external=True,
            simulation=False,
        )

    def read(self, uri: str) -> bytes:
        bucket, key = _split_s3(uri)
        return self._client().get_object(Bucket=bucket, Key=key)["Body"].read()

    def verify(self, uri: str, digest: str) -> bool:
        return sha256_bytes(self.read(uri)) == digest


class LocalDataLake:
    mode = "local"
    simulation = False
    external = False

    def __init__(self, root: str | None = None):
        self.root = Path(root or settings.lab_lake_dir)

    def write_harmonized(self, experiment_id: str, run_id: str, dataset: dict) -> dict:
        dest = self.root / experiment_id / f"{run_id}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(dataset, indent=2, default=str))
        return {
            "uri": str(dest),
            "mode": self.mode,
            "external": False,
            "simulation": False,
            "format": "json",
        }


class S3DataLake:
    mode = "s3"
    simulation = False
    external = True

    def __init__(self, bucket: str):
        self.bucket = bucket

    def write_harmonized(self, experiment_id: str, run_id: str, dataset: dict) -> dict:
        import boto3

        key = f"lab/lake/{experiment_id}/{run_id}.json"
        boto3.client("s3", region_name=settings.aws_region or None).put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(dataset, default=str).encode(),
            ContentType="application/json",
        )
        return {
            "uri": f"s3://{self.bucket}/{key}",
            "mode": self.mode,
            "external": True,
            "simulation": False,
            "format": "json",
        }


class ElnSimulationAdapter:
    """Build-later ELN attachment. This adapter never calls an external ELN."""

    mode = "simulation"
    simulation = True
    external = False

    def attach_report(self, dossier_id: str, title: str) -> dict:
        return {
            "attached": False,
            "simulation": True,
            "external_called": False,
            "mode": "simulation",
            "dossier_id": dossier_id,
            "title": title,
            "message": "SIMULATION — ELN attachment is build-later. No external ELN was called.",
        }


class EnvSecretProvider:
    """Current secret source is process settings. A vault backend is not configured."""

    mode = "env"

    def status(self) -> dict:
        backend = (settings.lab_secret_backend or "env").lower()
        if backend in {"aws-secrets-manager", "vault"}:
            return {
                "backend": backend,
                "available": False,
                "message": "Requested secret vault is not connected. Lab code is not reading a vault.",
            }
        return {
            "backend": "env",
            "available": True,
            "message": "Secrets remain in the existing process settings. No vault is configured in this environment.",
        }


def landing_zone():
    if settings.lab_landing_bucket:
        return S3LandingZone(settings.lab_landing_bucket)
    return LocalLandingZone()


def data_lake():
    if settings.lab_lake_bucket:
        return S3DataLake(settings.lab_lake_bucket)
    return LocalDataLake()


def eln_adapter():
    return ElnSimulationAdapter()


def _split_s3(uri: str) -> tuple[str, str]:
    rest = uri.removeprefix("s3://")
    bucket, _, key = rest.partition("/")
    return bucket, key
