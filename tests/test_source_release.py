"""Exercise the action entry point without contacting GitHub or publishing."""

import datetime as dt
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from zoneinfo import ZoneInfo


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/source_release.sh"


class SourceReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "src").mkdir()
        (self.root / "src/tool").write_text("echo hello\n")
        (self.root / "bin").mkdir()
        gh = self.root / "bin/gh"
        gh.write_text(
            '#!/bin/bash\n'
            'printf "%s\\n" "$*" >> "$GH_CALL_LOG"\n'
            'if [[ "$1 $2" == "release view" ]]; then\n'
            '  [[ "${EXISTING_RELEASE:-false}" == true ]]\n'
            'elif [[ "$1 $2" == "release create" ]]; then\n'
            '  exit 0\n'
            'else\n'
            '  exit 99\n'
            'fi\n'
        )
        gh.chmod(0o755)
        self.calls = self.root / "gh-calls"
        self.env = {
            **os.environ,
            "PATH": f"{self.root / 'bin'}:{os.environ['PATH']}",
            "GH_CALL_LOG": str(self.calls),
            "VERSION_FILE": "VERSION",
            "VALIDATE_COMMAND": "test -f src/tool && touch validated",
            "PROJECT_NAME": "example",
            "PACKAGE_PATHS": "VERSION\nsrc",
            "GITHUB_OUTPUT": str(self.root / "outputs"),
            "GITHUB_SHA": "a" * 40,
        }
        # Never allow the parent process's mode to affect default-mode tests.
        self.env.pop("PUBLISH", None)

    def run_release(self, version="2020.01.01.1", publish="false", **env):
        (self.root / "VERSION").write_text(version + "\n")
        overrides = {} if publish is None else {"PUBLISH": publish}
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            cwd=self.root,
            env={**self.env, **overrides, **env},
            text=True, capture_output=True, check=False,
        )

    def today(self):
        return dt.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y.%m.%d") + ".1"

    def test_dry_run_builds_old_version_twice_without_github_calls(self):
        result = self.run_release(EXISTING_RELEASE="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("two archives are identical", result.stdout)
        self.assertFalse(self.calls.exists())
        self.assertTrue((self.root / "validated").exists())
        self.assertTrue((self.root / "dist/example-2020.01.01.1.tar.gz").is_file())
        self.assertTrue((self.root / "dist/example-2020.01.01.1.tar.gz.sha256").is_file())
        self.assertEqual((self.root / "VERSION").read_text(), "2020.01.01.1\n")
        self.assertEqual((self.root / "outputs").read_text(), "version=2020.01.01.1\ntag=v2020.01.01.1\n")

    def test_publish_defaults_to_true(self):
        result = self.run_release(version=self.today(), publish=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls.read_text().splitlines()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], f"release view v{self.today()}")
        self.assertTrue(calls[1].startswith(f"release create v{self.today()} "))
        self.assertIn("--target " + "a" * 40, calls[1])

    def test_publish_rejects_stale_date_before_github_or_build(self):
        result = self.run_release(publish="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match release date", result.stderr)
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root / "validated").exists())

    def test_publish_rejects_existing_release_before_build(self):
        result = self.run_release(version=self.today(), publish="true", EXISTING_RELEASE="true")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(self.calls.read_text(), f"release view v{self.today()}\n")
        self.assertFalse((self.root / "validated").exists())

    def test_invalid_publish_values_fail_closed(self):
        for value in ("", "False", "TRUE", "0", "yes", "false "):
            with self.subTest(value=value):
                result = self.run_release(publish=value)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("publish must be exactly true or false", result.stderr)
                self.assertFalse(self.calls.exists())
                self.assertFalse((self.root / "validated").exists())

    def test_dry_run_still_rejects_invalid_calendar_version(self):
        result = self.run_release(version="2020.02.30.1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.calls.exists())
        self.assertFalse((self.root / "validated").exists())

    def test_failed_validation_never_publishes(self):
        result = self.run_release(version=self.today(), publish="true", VALIDATE_COMMAND="exit 17")
        self.assertEqual(result.returncode, 17)
        self.assertEqual(self.calls.read_text(), f"release view v{self.today()}\n")
        self.assertFalse((self.root / "dist").exists())


if __name__ == "__main__":
    unittest.main()
