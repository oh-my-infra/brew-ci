#!/usr/bin/env python3
"""Create a reproducible source archive for a GitHub Release."""

from __future__ import annotations

import argparse
import gzip
import tarfile
from pathlib import Path


def archive_inputs(paths: list[Path]) -> list[Path]:
    members: list[Path] = []
    for path in paths:
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"input must stay within the repository: {path}")
        if path.is_dir():
            members.append(path)
            members.extend(sorted(path.rglob("*")))
        elif path.exists() or path.is_symlink():
            members.append(path)
        else:
            raise FileNotFoundError(path)
    return sorted(set(members), key=lambda item: item.as_posix())


def normalized_info(archive: tarfile.TarFile, path: Path, prefix: str) -> tarfile.TarInfo:
    member = archive.gettarinfo(path, arcname=f"{prefix}/{path.as_posix()}")
    member.uid = member.gid = 0
    member.uname = member.gname = ""
    member.mtime = 0
    member.mode = 0o755 if path.is_dir() or member.mode & 0o111 else 0o644
    return member


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    prefix = f"{args.name}-{args.version}"
    with args.output.open("wb") as raw:
        with gzip.GzipFile(
            fileobj=raw,
            mode="wb",
            filename="",
            mtime=0,
            compresslevel=9,
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in archive_inputs(args.paths):
                    info = normalized_info(archive, path, prefix)
                    if path.is_file() and not path.is_symlink():
                        with path.open("rb") as source:
                            archive.addfile(info, source)
                    else:
                        archive.addfile(info)


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        raise SystemExit(str(error)) from error
