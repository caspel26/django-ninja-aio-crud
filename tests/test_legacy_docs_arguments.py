"""Legacy docs arguments must be rejected before filesystem or CLI effects."""
import importlib.util
from pathlib import Path
import sys
from unittest import mock

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


with mock.patch.dict(sys.modules, {"home": load_module("legacy_docs_home", ROOT / "docs-legacy/home.py")}):
    migrate = load_module("legacy_docs_migrate", ROOT / "docs-legacy/migrate.py")


class LegacyDocsArgumentTests(SimpleTestCase):
    def test_numeric_versions_remain_supported(self):
        for version in ("1.0", "1.12.3", "2.0", "2.36"):
            self.assertEqual(migrate.validate_version(version), version)
        self.assertEqual(migrate.install_command("2.36"), "pip install django-ninja-aio-crud~=2.36.0")

    def test_bad_versions_never_reach_git_or_filesystem_preparation(self):
        for version in ("--help", "../../outside", "2../outside", "2.36/../../outside", '2.36"\nextra: bad', "2.36;echo bad", "2.36\n", "latest", "3.0"):
            with self.subTest(version=version), mock.patch.object(migrate.subprocess, "run") as run, mock.patch.object(migrate.shutil, "copytree") as copytree:
                with self.assertRaises(ValueError):
                    migrate.prepare(version, "5a07d01", Path("/tmp/legacy-argument-test"))
                run.assert_not_called()
                copytree.assert_not_called()
                with self.assertRaises(ValueError):
                    migrate.install_command(version)
                with self.assertRaises(ValueError):
                    migrate.patch_config(Path("/does-not-exist"), version)

    def test_bad_commits_are_rejected_before_git_runs(self):
        for commit in ("--help", "HEAD", "main:path", "5a07d01\n", "5a07d01;echo bad"):
            with self.subTest(commit=commit), mock.patch.object(migrate.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    migrate.prepare("2.36", commit, Path("/tmp/legacy-argument-test"))
                run.assert_not_called()

    def test_history_only_selects_valid_versions_and_object_ids(self):
        history = "\n".join([
            "Deployed 5a07d01 to 2.36 with MkDocs 1.6.1 and mike 2.1.3",
            "Deployed abcdef12 to 1.0.0",
            "Deployed abcdef13 to 2..",
            "Deployed not_a_hash to 2.35",
            "Deployed abcdef14 to 2.36evil",
        ])
        with mock.patch.object(migrate, "git", return_value=history):
            self.assertEqual(migrate.source_commits(), {"2.36": "5a07d01", "1.0.0": "abcdef12"})

    def test_invalid_cli_version_is_rejected_before_reading_history(self):
        with mock.patch.object(sys, "argv", ["migrate.py", "build", "--out", "/tmp/unused", "2.36/../../outside"]), mock.patch.object(migrate, "published_versions") as published, mock.patch.object(migrate.tempfile, "mkdtemp") as mkdtemp:
            with self.assertRaises(SystemExit) as exit_status, mock.patch("sys.stderr"):
                migrate.main()
            self.assertEqual(exit_status.exception.code, 2)
            published.assert_not_called()
            mkdtemp.assert_not_called()

    def test_invalid_published_version_is_rejected_before_creating_worktrees(self):
        with mock.patch.object(sys, "argv", ["migrate.py", "deploy"]), mock.patch.object(migrate, "published_versions", return_value=[{"version": "2../outside"}]), mock.patch.object(migrate, "source_commits", return_value={}), mock.patch.object(migrate.tempfile, "mkdtemp") as mkdtemp:
            with self.assertRaises(SystemExit) as exit_status, mock.patch("sys.stderr"):
                migrate.main()
            self.assertEqual(exit_status.exception.code, 2)
            mkdtemp.assert_not_called()
