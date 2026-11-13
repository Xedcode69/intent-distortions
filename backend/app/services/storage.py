from pathlib import Path
import os
import tempfile
from .canonical_data import sha

class ContentStore:
    """Local content-addressed development storage; no claim of IPFS pinning."""
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True,exist_ok=True)

    def put(self, data: bytes):
        digest = sha(data).hex()
        path = self.directory / digest
        if path.exists():
            if sha(path.read_bytes()).hex() != digest:
                raise ValueError("Corrupt content-addressed file")
        else:
            with tempfile.NamedTemporaryFile(dir=self.directory,delete=False) as file:
                temp=Path(file.name);file.write(data);file.flush();os.fsync(file.fileno())
            try:os.replace(temp,path)
            finally:temp.unlink(missing_ok=True)
        return {"sha256":digest,"uri":f"/api/v1/content/{digest}"}

    def get(self, digest):
        if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("Invalid content hash")
        data = (self.directory/digest).read_bytes()
        if sha(data).hex()!=digest:
            raise ValueError("Content hash mismatch")
        return data

class S3ContentStore:
    """Write-once SHA-256 keys, server checksums and full read-back validation."""
    def __init__(self,settings,client=None):
        import boto3
        from botocore.config import Config
        self.bucket=settings.s3_bucket
        self.public_url=settings.artifact_public_url.rstrip("/")
        self.client=client or boto3.client("s3",region_name=settings.s3_region,
            config=Config(connect_timeout=5,read_timeout=30,retries={"max_attempts":3,"mode":"standard"}),
            endpoint_url=settings.s3_endpoint_url or None,
            aws_access_key_id=settings.s3_access_key_id or None,
            aws_secret_access_key=settings.s3_secret_access_key or None)

    def put(self,data):
        import base64
        from botocore.exceptions import ClientError
        digest=sha(data).hex();key=f"sha256/{digest}"
        media="image/png" if data.startswith(b"\x89PNG") else "image/svg+xml" if data.startswith(b"<svg") else "image/webp" if data.startswith(b"RIFF") else "application/json"
        try:
            self.client.put_object(Bucket=self.bucket,Key=key,Body=data,ContentType=media,
                CacheControl="public,max-age=31536000,immutable",IfNoneMatch="*",
                ChecksumSHA256=base64.b64encode(bytes.fromhex(digest)).decode())
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("PreconditionFailed","412"):raise
        if self.get(digest)!=data:raise ValueError("Object storage read-back mismatch")
        return {"sha256":digest,"uri":f"{self.public_url}/{key}"}

    def get(self,digest):
        if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest):raise ValueError("Invalid content hash")
        from botocore.exceptions import ClientError
        try:response=self.client.get_object(Bucket=self.bucket,Key=f"sha256/{digest}")
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey","404"):raise FileNotFoundError(digest) from exc
            raise
        data=response["Body"].read()
        if sha(data).hex()!=digest:raise ValueError("Object content hash mismatch")
        return data

def content_store(settings):
    return S3ContentStore(settings) if settings.storage_provider=="s3" else ContentStore(settings.data_dir/"content")
