"""Rebuild the published 1.x/2.x docs with the current (v3) theme.

Each version is rebuilt from the commit it was originally deployed from (read
from the ``gh-pages`` history), in its own git worktree, with the theme files
of the current checkout copied in. Pages and API reference stay those of the
original version; the home page is the v3 home, with its links pointing to
the latest docs.

Usage (from the repository root, with the docs requirements installed):

    # Build every published version into a local folder to preview it
    python docs-legacy/migrate.py build --out /tmp/legacy-site
    python -m http.server -d /tmp/legacy-site 8769

    # Build only some versions
    python docs-legacy/migrate.py build --out /tmp/legacy-site 2.36 2.0

    # Redeploy with mike (commits to the local gh-pages branch, no push)
    python docs-legacy/migrate.py deploy

Set GITHUB_TOKEN so the release notes page can read the GitHub releases.
"""

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

from home import render_home

REPO = pathlib.Path(__file__).resolve().parent.parent
HERE = pathlib.Path(__file__).resolve().parent
PAGES_BRANCH = "origin/gh-pages"
THEME_CSS = ["tokens.css", "shell.css", "components.css", "pages.css", "legacy.css"]
THEME_JS = ["theme.js", "a11y.js", "home.js"]
VERSION_PATTERN = r"[12]\.\d+(?:\.\d+)?"
COMMIT_PATTERN = r"[0-9a-fA-F]{7,64}"


def validate_version(version: str) -> str:
    if not re.fullmatch(VERSION_PATTERN, version, flags=re.ASCII):
        raise ValueError("Legacy versions must be numeric 1.x/2.x identifiers (for example 2.36 or 1.0.0)")
    return version


def validate_commit(commit: str) -> str:
    if not re.fullmatch(COMMIT_PATTERN, commit):
        raise ValueError("Deployment commits must be hexadecimal Git object IDs")
    return commit



def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True)


def published_versions() -> list[dict]:
    return json.loads(git("show", f"{PAGES_BRANCH}:versions.json"))


def source_commits() -> dict[str, str]:
    """Map each version to the commit of its most recent mike deploy."""
    commits: dict[str, str] = {}
    for subject in git("log", PAGES_BRANCH, "--format=%s").splitlines():
        match = re.fullmatch(rf"Deployed ({COMMIT_PATTERN}) to ({VERSION_PATTERN})(?: with .*)?", subject, flags=re.ASCII)
        if match and match.group(2) not in commits:
            commits[match.group(2)] = match.group(1)
    return commits


def top_level_block(text: str, key: str) -> tuple[int, int] | None:
    match = re.search(rf"^{key}:.*$", text, re.M)
    if not match:
        return None
    rest = re.search(r"^\S", text[match.end() + 1 :], re.M)
    end = match.end() + 1 + rest.start() if rest else len(text)
    return match.start(), end


def replace_block(text: str, key: str, block: str) -> str:
    span = top_level_block(text, key)
    if span is None:
        return text.rstrip("\n") + "\n\n" + block
    return text[: span[0]] + block + text[span[1] :]


def install_command(version: str) -> str:
    version = validate_version(version)
    parts = version.split(".")
    spec = ".".join(parts + ["0"] * (3 - len(parts)))
    return f"pip install django-ninja-aio-crud~={spec}"


def patch_config(worktree: pathlib.Path, version: str) -> None:
    version = validate_version(version)
    current = (REPO / "mkdocs.yml").read_text()
    start, end = top_level_block(current, "theme")
    config = worktree / "mkdocs.yml"
    text = replace_block(config.read_text(), "theme", current[start:end])
    site_url = re.search(r"^site_url:\s*(\S+)", current, re.M).group(1).rstrip("/")
    text = replace_block(text, "site_url", f"site_url: {site_url}/{version}/\n")
    text = re.sub(
        r"^extra:\n",
        f'extra:\n  nac_version: "{version}"\n  nac_install: "{install_command(version)}"\n',
        text,
        count=1,
        flags=re.M,
    )
    css = "".join(f"  - stylesheets/{name}\n" for name in THEME_CSS)
    js = "".join(f"  - javascripts/{name}\n" for name in THEME_JS)
    text = replace_block(text, "extra_css", f"extra_css:\n{css}\n")
    text = replace_block(text, "extra_javascript", f"extra_javascript:\n{js}\n")
    config.write_text(text)


def adapt_home(worktree: pathlib.Path) -> None:
    import yaml

    index = worktree / "docs/index.md"
    if not index.exists():
        return
    text = index.read_text()
    meta: dict = {}
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if match:
        meta = yaml.safe_load(match.group(1)) or {}
    meta["template"] = "legacy_home.html"
    meta["hide"] = ["navigation", "toc", "footer"]
    index.write_text(f"---\n{yaml.safe_dump(meta, sort_keys=False)}---\n\n# django-ninja-aio-crud\n")


def prepare(version: str, commit: str, root: pathlib.Path) -> pathlib.Path:
    version = validate_version(version)
    commit = validate_commit(commit)
    worktree = root.resolve() / f"wt-{version}"
    if worktree.exists():
        subprocess.run(["git", "worktree", "remove", "--force", "--", str(worktree)], cwd=REPO, check=True)
    subprocess.run(["git", "worktree", "add", "--detach", "-q", "--", str(worktree), commit], cwd=REPO, check=True)

    shutil.rmtree(worktree / "overrides", ignore_errors=True)
    shutil.copytree(REPO / "overrides", worktree / "overrides", ignore=shutil.ignore_patterns("home.html"))
    (worktree / "overrides/legacy_home.html").write_text(render_home(worktree))
    shutil.copy(REPO / "main.py", worktree / "main.py")
    shutil.copy(REPO / "CHANGELOG.md", worktree / "CHANGELOG.md")
    shutil.copy(REPO / "docs/release_notes.md", worktree / "docs/release_notes.md")
    (worktree / "docs/extra.css").unlink(missing_ok=True)
    for sub in ("stylesheets", "javascripts", "images/brand", "assets/fonts"):
        shutil.copytree(REPO / "docs" / sub, worktree / "docs" / sub, dirs_exist_ok=True)
    shutil.copy(HERE / "legacy.css", worktree / "docs/stylesheets/legacy.css")
    patch_config(worktree, version)
    adapt_home(worktree)
    return worktree


def preview_directory(value: str) -> pathlib.Path:
    """Confine preview writes to the repository or the system temporary folder."""
    supplied = pathlib.Path(value).expanduser()
    if ".." in supplied.parts:
        raise ValueError("Preview output must not contain parent-directory traversal")
    resolved = supplied.resolve()
    allowed_roots = (REPO.resolve(), pathlib.Path(tempfile.gettempdir()).resolve())
    for root in allowed_roots:
        try:
            relative = resolved.relative_to(root)
        except ValueError:
            continue
        if relative.parts:
            return root / relative
    raise ValueError("Preview output must be a subdirectory of the repository or system temporary folder")


def preview_version_directory(output: pathlib.Path, version: str) -> pathlib.Path:
    target = output / validate_version(version)
    target.resolve().relative_to(output.resolve())
    return target


def export_preview_versions(output: pathlib.Path, published: list[dict]) -> None:
    output = preview_directory(str(output))
    metadata = (output / "versions.json").resolve()
    metadata.relative_to(output)
    output.mkdir(parents=True, exist_ok=True)
    metadata.write_text(json.dumps(published))


def selected_versions(requested, published, commits):
    wanted = requested or [v["version"] for v in published if v["version"].split(".")[0] in {"1", "2"}]
    wanted = [validate_version(version) for version in wanted]
    for version in wanted:
        if version in commits:
            validate_commit(commits[version])
    return wanted


def rebuild_version(version: str, commit: str | None, args, root: pathlib.Path) -> bool:
    if commit is None:
        print(f"[skip] {version}: no deploy commit found on {PAGES_BRANCH}")
        return False
    print(f"[{version}] rebuilding from {commit}", flush=True)
    worktree = prepare(version, commit, root)
    try:
        if args.mode == "build":
            target = preview_version_directory(args.out, version)
            command = [sys.executable, "-m", "mkdocs", "build", "-q", "-d", str(target)]
        else:
            command = [sys.executable, "-m", "mike", "deploy", "--ignore-remote-status", "--", version]
        result = subprocess.run(command, cwd=worktree, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr[-2000:])
        return result.returncode == 0
    finally:
        if not args.keep:
            subprocess.run(["git", "worktree", "remove", "--force", "--", str(worktree)], cwd=REPO, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["build", "deploy"])
    parser.add_argument("versions", nargs="*", type=validate_version, help="Versions to rebuild (default: all published 1.x/2.x)")
    parser.add_argument("--out", type=pathlib.Path, help="Preview directory within the repository or system temporary folder")
    parser.add_argument("--keep", action="store_true", help="Keep the worktrees after building")
    args = parser.parse_intermixed_args()
    if args.out is not None:
        try:
            args.out = preview_directory(str(args.out))
        except ValueError as exc:
            parser.error(str(exc))
    if args.mode == "build" and args.out is None:
        parser.error("build needs --out")

    published = published_versions()
    commits = source_commits()
    try:
        wanted = selected_versions(args.versions, published, commits)
    except ValueError as exc:
        parser.error(str(exc))
    root = pathlib.Path(tempfile.mkdtemp(prefix="nac-legacy-"))
    failed = []

    for version in wanted:
        if not rebuild_version(version, commits.get(version), args, root):
            failed.append(version)

    if args.mode == "build":
        export_preview_versions(args.out, published)
    if failed:
        print("Failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
