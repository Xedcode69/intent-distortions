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

def content_store(settings):
    return ContentStore(settings.data_dir/"content")
