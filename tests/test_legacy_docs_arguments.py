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


home = load_module("legacy_docs_home", ROOT / "docs-legacy/home.py")
with mock.patch.dict(sys.modules, {"home": home}):
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

    def test_preview_output_is_confined_and_traversal_is_rejected(self):
        import tempfile

        allowed = Path(tempfile.gettempdir()).resolve() / "legacy-preview-test"
        self.assertEqual(migrate.preview_directory(str(allowed)), allowed)
        for path in ("/etc/legacy-preview", str(allowed / ".." / "escaped"), str(migrate.REPO)):
            with self.subTest(path=path), self.assertRaises(ValueError):
                migrate.preview_directory(path)

    def test_preview_version_symlink_cannot_escape_output(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "output"
            outside = Path(root) / "outside"
            output.mkdir()
            outside.mkdir()
            (output / "2.36").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                migrate.preview_version_directory(output, "2.36")

    def test_unicode_digits_are_not_accepted_as_versions(self):
        with self.assertRaises(ValueError):
            migrate.validate_version("2.٣٦")


class LegacyHomeRenderingTests(SimpleTestCase):
    def test_old_releases_only_advertise_features_they_contain(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            output = home.render_home(Path(root))
        self.assertIn("Fully async", output)
        self.assertNotIn("MCP server", output)
        self.assertNotIn("Bulk operations", output)
        self.assertIn("add its routes to the API", output)
        self.assertNotRegex(output, r"@@[A-Z_]+@@")

    def test_feature_detection_and_benchmark_names_are_safe_in_generated_html(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            worktree = Path(root)
            files = {
                "ninja_aio/api.py": "def viewset(self): pass\n",
                "ninja_aio/models.py": "class Serializer(): pass\ndef action(): pass\ndef on(): pass\nclass SoftDelete: pass\n",
                "ninja_aio/views/api.py": "def bulk_create(): pass\n",
                "ninja_aio/admin.py": "def register_admin(): pass\n",
                "ninja_aio/mcp/__init__.py": "# MCP support\n",
                "docs/comparison.md": "| Operation | ninja-aio | <unsafe> |\n| List | 0.24 | 1.2 |\n",
                "docs/getting_started/quick_start.md": "# Quick start\n",
            }
            for name, content in files.items():
                path = worktree / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            output = home.render_home(worktree)
        self.assertIn("MCP server", output)
        self.assertIn("Bulk operations", output)
        self.assertIn("Plain Django models", output)
        self.assertIn("One decorator", output)
        self.assertIn("&lt;unsafe&gt;", output)
        self.assertNotIn("<unsafe>", output)
        self.assertIn('<ul class="nac-bars"', output)
        self.assertIn("0.24 ms", output)
        self.assertNotIn('role="table"', output)
        self.assertNotRegex(output, r"@@[A-Z_]+@@")


class LegacyMigrationCommandTests(SimpleTestCase):
    def test_build_deploy_failure_and_keep_use_the_expected_arguments(self):
        import json
        import tempfile

        for mode, returncode, keep in (("build", 0, False), ("deploy", 0, True), ("build", 1, False)):
            with self.subTest(mode=mode, returncode=returncode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "preview"
                worktree = root / "worktree"
                argv = ["migrate.py", mode, "--out", str(output), "2.36"]
                if keep:
                    argv.append("--keep")
                published = [{"version": "2.36"}]
                response = mock.Mock(returncode=returncode, stderr="build failed")
                with mock.patch.object(sys, "argv", argv), mock.patch.object(migrate, "published_versions", return_value=published), mock.patch.object(migrate, "source_commits", return_value={"2.36": "5a07d01"}), mock.patch.object(migrate.tempfile, "mkdtemp", return_value=str(root)), mock.patch.object(migrate, "prepare", return_value=worktree), mock.patch.object(migrate.subprocess, "run", return_value=response) as run, mock.patch("sys.stdout"):
                    self.assertEqual(migrate.main(), returncode)
                command = run.call_args_list[0].args[0]
                if mode == "build":
                    self.assertEqual(command[-1], str(output.resolve() / "2.36"))
                    self.assertEqual(json.loads((output / "versions.json").read_text()), published)
                else:
                    self.assertEqual(command[-2:], ["--", "2.36"])
                self.assertEqual(run.call_count, 1 if keep else 2)

    def test_unknown_version_is_reported_without_preparing_a_worktree(self):
        from types import SimpleNamespace

        with mock.patch.object(migrate, "prepare") as prepare, mock.patch("sys.stdout"):
            self.assertFalse(migrate.rebuild_version("2.36", None, SimpleNamespace(), Path("/tmp/unused")))
        prepare.assert_not_called()

    def test_existing_metadata_symlink_cannot_overwrite_an_outside_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "output"
            outside = Path(root) / "outside.json"
            output.mkdir()
            outside.write_text("original")
            (output / "versions.json").symlink_to(outside)
            with self.assertRaises(ValueError):
                migrate.export_preview_versions(output, [{"version": "2.36"}])
            self.assertEqual(outside.read_text(), "original")


class LegacyDocsIntegrationTests(SimpleTestCase):
    def test_preparation_preserves_page_metadata_and_copies_the_current_theme(self):
        import tempfile
        import yaml

        with tempfile.TemporaryDirectory() as root:
            worktree = Path(root).resolve() / "wt-2.36"
            (worktree / "docs").mkdir(parents=True)
            (worktree / "mkdocs.yml").write_text("site_name: Legacy\ntheme:\n  name: material\nextra:\n  old: kept\nnav: []\n")
            (worktree / "docs/index.md").write_text("---\ntitle: Legacy landing\n---\n# Old home\n")
            (worktree / "docs/extra.css").write_text("old styles")
            with mock.patch.object(migrate.subprocess, "run") as run:
                prepared = migrate.prepare("2.36", "5a07d01", Path(root))
            self.assertEqual(prepared, worktree)
            self.assertEqual(run.call_args_list[1].args[0][-3:], ["--", str(worktree), "5a07d01"])
            config = yaml.safe_load((worktree / "mkdocs.yml").read_text())
            self.assertEqual(config["extra"]["nac_version"], "2.36")
            self.assertEqual(config["extra"]["old"], "kept")
            self.assertIn("stylesheets/legacy.css", config["extra_css"])
            self.assertTrue((worktree / "docs/images/brand/mark-dark-64.png").is_file())
            self.assertTrue((worktree / "docs/assets/fonts/schibsted-grotesk-latin-wght.woff2").is_file())
            self.assertEqual((worktree / "main.py").read_text(), (ROOT / "main.py").read_text())
            self.assertEqual((worktree / "CHANGELOG.md").read_text(), (ROOT / "CHANGELOG.md").read_text())
            self.assertEqual((worktree / "docs/release_notes.md").read_text(), (ROOT / "docs/release_notes.md").read_text())
            self.assertEqual(config["site_url"], "https://django-ninja-aio.com/2.36/")
            self.assertFalse((worktree / "docs/extra.css").exists())
            self.assertFalse((worktree / "overrides/home.html").exists())
            self.assertIn("Legacy landing", (worktree / "docs/index.md").read_text())
            self.assertIn("legacy_home.html", (worktree / "docs/index.md").read_text())
            self.assertIn("Upgrade to 3.0", (worktree / "overrides/legacy_home.html").read_text())

    def test_legacy_home_without_frontmatter_and_missing_home_are_supported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            worktree = Path(root)
            migrate.adapt_home(worktree)
            (worktree / "docs").mkdir()
            (worktree / "docs/index.md").write_text("# Old home")
            migrate.adapt_home(worktree)
            self.assertIn("legacy_home.html", (worktree / "docs/index.md").read_text())
        result = migrate.replace_block("site_name: Legacy\n", "theme", "theme:\n  name: material\n")
        self.assertIn("site_name: Legacy", result)
        self.assertTrue(result.endswith("  name: material\n"))

    def test_published_metadata_is_read_as_json_without_invoking_a_shell(self):
        with mock.patch.object(migrate.subprocess, "check_output", return_value='[{"version":"2.36"}]') as command:
            self.assertEqual(migrate.published_versions(), [{"version": "2.36"}])
        self.assertEqual(command.call_args.args[0], ["git", "show", "origin/gh-pages:versions.json"])

    def test_preview_cli_rejects_missing_or_outside_output_before_running_git(self):
        for argv in (["migrate.py", "build"], ["migrate.py", "build", "--out", "/etc/legacy-preview"]):
            with self.subTest(argv=argv), mock.patch.object(sys, "argv", argv), mock.patch.object(migrate, "published_versions") as published, mock.patch("sys.stderr"):
                with self.assertRaises(SystemExit) as exit_status:
                    migrate.main()
                self.assertEqual(exit_status.exception.code, 2)
            published.assert_not_called()

    def test_help_entry_point_does_not_read_history_or_build_anything(self):
        import runpy

        with mock.patch.object(sys, "argv", ["migrate.py", "--help"]), mock.patch.dict(sys.modules, {"home": home}), mock.patch("subprocess.check_output") as git, mock.patch("sys.stdout"):
            with self.assertRaises(SystemExit) as exit_status:
                runpy.run_path(str(ROOT / "docs-legacy/migrate.py"), run_name="__main__")
        self.assertEqual(exit_status.exception.code, 0)
        git.assert_not_called()

    def test_partial_or_zero_benchmarks_do_not_break_legacy_rendering(self):
        import tempfile

        with tempfile.TemporaryDirectory() as root:
            worktree = Path(root)
            (worktree / "docs").mkdir()
            page = worktree / "docs/comparison.md"
            page.write_text("# No benchmark table")
            self.assertEqual(home._benchmarks(worktree), "")
            page.write_text("| Operation | ninja-aio |\n| List | n/a |\n")
            self.assertEqual(home._benchmarks(worktree), "")
            page.write_text("| Operation | ninja-aio | Other |\n| List | 0.0 | 0.0 |\n")
            self.assertIn("0.00 ms", home._benchmarks(worktree))
            (worktree / "ninja_aio/views").mkdir(parents=True)
            (worktree / "ninja_aio/models.py").write_text("class Serializer(): pass\n")
            (worktree / "ninja_aio/views/api.py").write_text("def bulk_create(): pass\n")
            self.assertIn("Bulk operations", home.render_home(worktree))
