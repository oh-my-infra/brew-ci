#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
BETA_SCRIPT = ROOT / "scripts/source_beta.sh"
PROMOTE_SCRIPT = ROOT / "scripts/promote_source_beta.sh"
PACKAGER = ROOT / "scripts/package_release.py"


class BetaReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src/tool").write_text("#!/bin/sh\necho ok\n")
        (self.root / "src/tool").chmod(0o755)
        (self.root / "bin").mkdir()
        self.calls = self.root / "gh-calls"
        gh = self.root / "bin/gh"
        gh.write_text(
            '#!/bin/bash\n'
            'printf "%s\\n" "$*" >> "$GH_CALL_LOG"\n'
            'if [[ "$1 $2" == "release view" ]]; then\n'
            '  exit 1\n'
            'elif [[ "$1 $2" == "release create" ]]; then\n'
            '  exit 0\n'
            'fi\n'
            'exit 99\n'
        )
        gh.chmod(0o755)
        self.version = dt.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y.%m.%d") + ".1"
        (self.root / "VERSION").write_text(self.version + "\n")
        self.env = {
            **os.environ,
            "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}",
            "GH_CALL_LOG": str(self.calls),
            "VERSION_FILE": "VERSION",
            "VALIDATE_COMMAND": "test -f src/tool && touch validated",
            "PROJECT_NAME": "example",
            "PACKAGE_PATHS": "VERSION\nsrc",
            "BETA_NUMBER": "1",
            "GITHUB_OUTPUT": str(self.root / "outputs"),
            "SOURCE_COMMIT": "a" * 40,
            "GITHUB_SHA": "b" * 40,
        }

    def test_beta_is_prerelease_and_archive_is_reproducible(self) -> None:
        result = subprocess.run(
            ["/bin/bash", str(BETA_SCRIPT)], cwd=self.root, env=self.env,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        tag = f"v{self.version}-beta.1"
        calls = self.calls.read_text().splitlines()
        self.assertEqual(calls[:2], [f"release view {tag}", f"release view v{self.version}"])
        self.assertIn(f"release create {tag} ", calls[2])
        self.assertIn(" --prerelease ", calls[2])
        self.assertIn("--target " + "a" * 40, calls[2])
        self.assertNotIn("b" * 40, calls[2])
        self.assertTrue((self.root / f"dist/example-{self.version}.tar.gz").is_file())
        self.assertEqual(
            (self.root / "outputs").read_text(),
            f"version={self.version}\ntag={tag}\nsha256="
            + subprocess.check_output(
                ["shasum", "-a", "256", f"dist/example-{self.version}.tar.gz"],
                cwd=self.root, text=True,
            ).split()[0]
            + "\n",
        )

    def test_beta_number_fails_closed(self) -> None:
        result = subprocess.run(
            ["/bin/bash", str(BETA_SCRIPT)], cwd=self.root,
            env={**self.env, "BETA_NUMBER": "01"}, text=True, capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("beta-number", result.stderr)
        self.assertFalse(self.calls.exists())

    def test_source_commit_must_be_an_explicit_full_sha(self) -> None:
        result = subprocess.run(
            ["/bin/bash", str(BETA_SCRIPT)], cwd=self.root,
            env={**self.env, "SOURCE_COMMIT": "main"}, text=True, capture_output=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source-commit", result.stderr)
        self.assertFalse(self.calls.exists())


class PromotionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=self.root, check=True)
        self.version = "2026.10.19.1"
        (self.root / "VERSION").write_text(self.version + "\n")
        (self.root / "tool").write_text("ok\n")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "candidate"], cwd=self.root, check=True)
        self.sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.root, text=True).strip()
        self.upstream = self.root / "upstream.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.upstream)], check=True)
        subprocess.run(["git", "remote", "add", "origin", str(self.upstream)], cwd=self.root, check=True)
        subprocess.run(["git", "push", "-q", "origin", "HEAD:master"], cwd=self.root, check=True)
        self.assets = self.root / "candidate-assets"
        self.assets.mkdir()
        archive = self.assets / f"example-{self.version}.tar.gz"
        subprocess.run(
            ["python3", str(PACKAGER), "--name", "example", "--version", self.version,
             "--output", str(archive), "VERSION", "tool"],
            cwd=self.root, check=True,
        )
        checksum = subprocess.check_output(
            ["shasum", "-a", "256", archive.name], cwd=self.assets, text=True,
        )
        (self.assets / f"{archive.name}.sha256").write_text(checksum)
        self.approved_sha256 = checksum.split()[0]
        (self.root / "bin").mkdir()
        self.calls = self.root / "gh-calls"
        gh = self.root / "bin/gh"
        gh.write_text(
            '#!/bin/bash\n'
            'printf "%s\\n" "$*" >> "$GH_CALL_LOG"\n'
            'if [[ "$1 $2 $4" == "release view --json"* ]]; then printf "true\\n"; exit 0; fi\n'
            'if [[ "$1 $2" == "release view" ]]; then exit 1; fi\n'
            'if [[ "$1" == api && "$2" == */git/ref/tags/* ]]; then printf "%s\\n" "$CANDIDATE_SHA"; exit 0; fi\n'
            'if [[ "$1" == api && "$2" == "repos/owner/example" ]]; then printf "master\\n"; exit 0; fi\n'
            'if [[ "$1 $2" == "release download" ]]; then\n'
            '  destination=""\n'
            '  while [[ $# -gt 0 ]]; do\n'
            '    if [[ "$1" == --dir ]]; then destination="$2"; shift 2; else shift; fi\n'
            '  done\n'
            '  cp "$CANDIDATE_ASSETS"/* "$destination/"; exit 0\n'
            'fi\n'
            'if [[ "$1 $2" == "release create" ]]; then exit 0; fi\n'
            'exit 99\n'
        )
        gh.chmod(0o755)
        self.output = self.root / "outputs"
        self.env = {
            **os.environ,
            "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}",
            "GH_CALL_LOG": str(self.calls),
            "CANDIDATE_SHA": self.sha,
            "CANDIDATE_ASSETS": str(self.assets),
            "PROJECT_NAME": "example",
            "BETA_TAG": f"v{self.version}-beta.1",
            "EXPECTED_SHA256": self.approved_sha256,
            "GITHUB_REPOSITORY": "owner/example",
            "GITHUB_OUTPUT": str(self.output),
        }

    def test_promotion_reuses_candidate_assets(self) -> None:
        result = subprocess.run(
            ["/bin/bash", str(PROMOTE_SCRIPT)], cwd=self.root, env=self.env,
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls.read_text()
        self.assertIn(f"release download v{self.version}-beta.1", calls)
        self.assertIn(f"release create v{self.version} ", calls)
        self.assertIn(f"--target {self.sha}", calls)
        self.assertIn(f"candidate-tag=v{self.version}-beta.1", self.output.read_text())

    def test_promotion_rejects_digest_not_explicitly_approved(self) -> None:
        result = subprocess.run(
            ["/bin/bash", str(PROMOTE_SCRIPT)], cwd=self.root,
            env={**self.env, "EXPECTED_SHA256": "0" * 64},
            text=True, capture_output=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approved digest", result.stderr)
        self.assertNotIn(f"release create v{self.version} ", self.calls.read_text())


if __name__ == "__main__":
    unittest.main()
