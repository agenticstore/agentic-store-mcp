"""Safe, read-only ZIP and TAR archive inventory."""
import tarfile
import zipfile
from pathlib import Path
from typing import Any

_MAX_ENTRIES = 5_000


def _zip_entries(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        return [{"path": item.filename, "size_bytes": item.file_size, "compressed_bytes": item.compress_size,
                 "directory": item.is_dir()} for item in archive.infolist()[:_MAX_ENTRIES]]


def _tar_entries(path: Path) -> list[dict[str, Any]]:
    with tarfile.open(path, "r:*") as archive:
        return [{"path": item.name, "size_bytes": item.size, "directory": item.isdir(),
                 "type": "symlink" if item.issym() else "file"} for item in archive.getmembers()[:_MAX_ENTRIES]]


def run(params: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(params.get("path") or "").strip()).expanduser().resolve()
    if not path.is_file():
        return {"result": None, "error": f"Archive not found: {path}"}
    try:
        if zipfile.is_zipfile(path):
            entries, archive_type = _zip_entries(path), "zip"
        elif tarfile.is_tarfile(path):
            entries, archive_type = _tar_entries(path), "tar"
        else:
            return {"result": None, "error": "Supported archives: ZIP, TAR, TAR.GZ, TAR.BZ2, TAR.XZ"}
        max_entries = max(1, min(int(params.get("max_entries", 200)), _MAX_ENTRIES))
        return {"result": {"path": str(path), "archive_type": archive_type, "entries": entries[:max_entries],
                "entry_count": len(entries), "truncated": len(entries) >= max_entries, "read_only": True}, "error": None}
    except (OSError, tarfile.TarError, zipfile.BadZipFile) as exc:
        return {"result": None, "error": f"Unable to inspect archive: {exc}"}
