"""
Ground Truth Storage — S3 with local filesystem fallback.

Usage:
    from agent_platform.gt_storage import GTStorage
    storage = GTStorage()

    # Save
    storage.save("marketing_agent_queries.json", data_dict)

    # Load
    data = storage.load("marketing_agent_queries.json")   # None if not found

    # Check existence
    if storage.exists("marketing_agent_queries.json"):
        ...
"""
import json
import os
from loguru import logger

_GT_LOCAL_DIR = "data/ground_truth"
_GT_S3_PREFIX = "ground_truth"


class GTStorage:
    """
    Unified Ground Truth storage.
    - When GT_S3_BUCKET env var is set  → reads/writes to S3
    - Otherwise                          → reads/writes to local data/ground_truth/
    """

    def __init__(self):
        self.bucket = os.environ.get("GT_S3_BUCKET", "")
        self.region = os.environ.get("AWS_REGION", "eu-north-1")
        self._s3 = None

        if self.bucket:
            try:
                import boto3
                self._s3 = boto3.client("s3", region_name=self.region)
                logger.info(f"GTStorage: using S3 bucket '{self.bucket}'")
            except Exception as e:
                logger.warning(f"GTStorage: boto3 unavailable, falling back to local — {e}")
                self._s3 = None
        else:
            logger.info("GTStorage: GT_S3_BUCKET not set, using local filesystem")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def save(self, filename: str, data: dict) -> bool:
        """Save dict as JSON. Returns True on success."""
        if self._s3:
            return self._s3_put(filename, data)
        return self._local_put(filename, data)

    def load(self, filename: str) -> dict | None:
        """Load JSON as dict. Returns None if not found."""
        if self._s3:
            return self._s3_get(filename)
        return self._local_get(filename)

    def exists(self, filename: str) -> bool:
        """Check if file exists."""
        if self._s3:
            return self._s3_exists(filename)
        return self._local_exists(filename)

    # ------------------------------------------------------------------ #
    # S3 operations
    # ------------------------------------------------------------------ #

    def _s3_key(self, filename: str) -> str:
        return f"{_GT_S3_PREFIX}/{filename}"

    def _s3_put(self, filename: str, data: dict) -> bool:
        try:
            body = json.dumps(data, indent=2, default=str)
            self._s3.put_object(
                Bucket=self.bucket,
                Key=self._s3_key(filename),
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )
            logger.info(f"GTStorage: saved s3://{self.bucket}/{self._s3_key(filename)}")
            return True
        except Exception as e:
            logger.error(f"GTStorage: S3 put failed for {filename} — {e}")
            return False

    def _s3_get(self, filename: str) -> dict | None:
        try:
            resp = self._s3.get_object(Bucket=self.bucket, Key=self._s3_key(filename))
            data = json.loads(resp["Body"].read().decode("utf-8"))
            logger.info(f"GTStorage: loaded s3://{self.bucket}/{self._s3_key(filename)}")
            return data
        except self._s3.exceptions.NoSuchKey:
            logger.warning(f"GTStorage: not found in S3 — {filename}")
            return None
        except Exception as e:
            logger.error(f"GTStorage: S3 get failed for {filename} — {e}")
            return None

    def _s3_exists(self, filename: str) -> bool:
        try:
            self._s3.get_object_attributes(
                Bucket=self.bucket,
                Key=self._s3_key(filename),
                ObjectAttributes=["ETag"],
            )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Local filesystem operations
    # ------------------------------------------------------------------ #

    def _local_path(self, filename: str) -> str:
        return os.path.join(_GT_LOCAL_DIR, filename)

    def _local_put(self, filename: str, data: dict) -> bool:
        try:
            os.makedirs(_GT_LOCAL_DIR, exist_ok=True)
            path = self._local_path(filename)
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"GTStorage: saved locally to {path}")
            return True
        except Exception as e:
            logger.error(f"GTStorage: local put failed for {filename} — {e}")
            return False

    def _local_get(self, filename: str) -> dict | None:
        path = self._local_path(filename)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"GTStorage: local get failed for {filename} — {e}")
            return None

    def _local_exists(self, filename: str) -> bool:
        return os.path.exists(self._local_path(filename))


# Module-level singleton
_storage_instance: GTStorage | None = None


def get_gt_storage() -> GTStorage:
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = GTStorage()
    return _storage_instance
