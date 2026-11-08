"""Read a screenplay pack from a directory or a ZIP. Nothing is extracted or modified."""
from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Optional


@dataclass(frozen=True)
class SourceFile:
    name: str                   # file name only, never an absolute path
    folder: str                 # parent folder inside the pack ("" for the root)
    sha256: str
    text: Optional[str]         # None when the bytes could not be decoded
    decode_error: Optional[str] = None


@dataclass(frozen=True)
class SourcePack:
    title: str
    origin: str                 # "zip" | "directory"
    files: list[SourceFile]


def _natural_key(name: str) -> list:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", name)]


def _decode(name: str, folder: str, data: bytes) -> SourceFile:
    digest = hashlib.sha256(data).hexdigest()
    try:
        return SourceFile(name, folder, digest, data.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        return SourceFile(name, folder, digest, None, f"not valid UTF-8: {exc}")


def _is_screenplay(path: PurePosixPath) -> bool:
    return (
        path.suffix.lower() == ".txt"
        and not path.name.startswith(".")
        and "__MACOSX" not in path.parts
    )


def _title_from(folders: set[str], fallback: str) -> str:
    # One show per pack: the folder holding the episodes names the show.
    if len(folders) == 1:
        only = next(iter(folders))
        if only:
            return PurePosixPath(only).name
    return fallback


def load_pack(path: str | Path) -> SourcePack:
    path = Path(path)
    if path.is_dir():
        files = []
        for file in path.rglob("*.txt"):
            rel = PurePosixPath(file.relative_to(path).as_posix())
            if _is_screenplay(rel):
                files.append(_decode(rel.name, str(rel.parent) if str(rel.parent) != "." else "", file.read_bytes()))
        origin, fallback = "directory", path.name
    elif zipfile.is_zipfile(path):
        files = []
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                rel = PurePosixPath(info.filename)
                if not info.is_dir() and _is_screenplay(rel):
                    parent = str(rel.parent) if str(rel.parent) != "." else ""
                    files.append(_decode(rel.name, parent, archive.read(info)))
        origin, fallback = "zip", path.stem
    else:
        raise FileNotFoundError(f"Not a directory or ZIP file: {path}")

    files.sort(key=lambda f: (_natural_key(f.folder), _natural_key(f.name)))
    title = _title_from({f.folder for f in files}, fallback)
    return SourcePack(title=title, origin=origin, files=files)
