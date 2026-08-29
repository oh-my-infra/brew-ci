#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_version.py"
PACKAGER = ROOT / "scripts/package_release.py"


class VersionTests(unittest.TestCase):
    def run_validator(self, version: str, today: str = "2026-08-29") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), version, "--today", today],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_accepts_canonical_calver(self) -> None:
        result = self.run_validator("2026.08.29.1")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_missing_revision(self) -> None:
        self.assertNotEqual(self.run_validator("2026.08.29").returncode, 0)

    def test_rejects_zero_padded_revision(self) -> None:
        self.assertNotEqual(self.run_validator("2026.08.29.01").returncode, 0)

    def test_rejects_invalid_date(self) -> None:
        self.assertNotEqual(self.run_validator("2026.02.30.1").returncode, 0)

    def test_rejects_stale_release_date(self) -> None:
        self.assertNotEqual(self.run_validator("2026.08.28.1").returncode, 0)


class PackagingTests(unittest.TestCase):
    def test_archive_is_reproducible_and_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/tool").write_text("#!/bin/sh\necho ok\n")
            (root / "src/tool").chmod(0o755)
            (root / "VERSION").write_text("2026.08.29.1\n")

            outputs = [root / "one.tar.gz", root / "two.tar.gz"]
            for output in outputs:
                subprocess.run(
                    [
                        sys.executable,
                        str(PACKAGER),
                        "--name",
                        "example",
                        "--version",
                        "2026.08.29.1",
                        "--output",
                        str(output),
                        "VERSION",
                        "src",
                    ],
                    cwd=root,
                    check=True,
                )

            digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in outputs]
            self.assertEqual(digests[0], digests[1])

            with tarfile.open(fileobj=io.BytesIO(outputs[0].read_bytes()), mode="r:gz") as archive:
                names = archive.getnames()
                self.assertEqual(
                    names,
                    [
                        "example-2026.08.29.1/VERSION",
                        "example-2026.08.29.1/src",
                        "example-2026.08.29.1/src/tool",
                    ],
                )
                for member in archive.getmembers():
                    self.assertEqual(member.uid, 0)
                    self.assertEqual(member.gid, 0)
                    self.assertEqual(member.mtime, 0)


if __name__ == "__main__":
    unittest.main()
