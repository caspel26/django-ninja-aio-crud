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

import yaml
from home import render_home

REPO = pathlib.Path(__file__).resolve().parent.parent
HERE = pathlib.Path(__file__).resolve().parent
PAGES_BRANCH = "origin/gh-pages"
THEME_CSS = ["tokens.css", "shell.css", "components.css", "pages.css", "legacy.css"]
THEME_JS = ["theme.js", "a11y.js", "home.js"]



def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True)


def published_versions() -> list[dict]:
    return json.loads(git("show", f"{PAGES_BRANCH}:versions.json"))


def source_commits() -> dict[str, str]:
    """Map each version to the commit of its most recent mike deploy."""
    commits: dict[str, str] = {}
    for subject in git("log", PAGES_BRANCH, "--format=%s").splitlines():
        match = re.match(r"Deployed (\w+) to ([\w.]+)", subject)
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
    parts = version.split(".")
    spec = ".".join(parts + ["0"] * (3 - len(parts)))
    return f"pip install django-ninja-aio-crud~={spec}"


def patch_config(worktree: pathlib.Path, version: str) -> None:
    current = (REPO / "mkdocs.yml").read_text()
    start, end = top_level_block(current, "theme")
    config = worktree / "mkdocs.yml"
    text = replace_block(config.read_text(), "theme", current[start:end])
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
    worktree = root / f"wt-{version}"
    if worktree.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=REPO, check=True)
    subprocess.run(["git", "worktree", "add", "--detach", "-q", str(worktree), commit], cwd=REPO, check=True)

    shutil.rmtree(worktree / "overrides", ignore_errors=True)
    shutil.copytree(REPO / "overrides", worktree / "overrides", ignore=shutil.ignore_patterns("home.html"))
    (worktree / "overrides/legacy_home.html").write_text(render_home(worktree))
    (worktree / "docs/extra.css").unlink(missing_ok=True)
    for sub in ("stylesheets", "javascripts", "images/brand"):
        shutil.copytree(REPO / "docs" / sub, worktree / "docs" / sub, dirs_exist_ok=True)
    shutil.copy(HERE / "legacy.css", worktree / "docs/stylesheets/legacy.css")
    patch_config(worktree, version)
    adapt_home(worktree)
    return worktree


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=["build", "deploy"])
    parser.add_argument("versions", nargs="*", help="Versions to rebuild (default: all published 1.x/2.x)")
    parser.add_argument("--out", type=pathlib.Path, help="Output folder for build mode")
    parser.add_argument("--keep", action="store_true", help="Keep the worktrees after building")
    args = parser.parse_args()
    if args.mode == "build" and args.out is None:
        parser.error("build needs --out")

    published = published_versions()
    commits = source_commits()
    wanted = args.versions or [v["version"] for v in published if v["version"].split(".")[0] in {"1", "2"}]
    root = pathlib.Path(tempfile.mkdtemp(prefix="nac-legacy-"))
    failed = []

    for version in wanted:
        commit = commits.get(version)
        if commit is None:
            print(f"[skip] {version}: no deploy commit found on {PAGES_BRANCH}")
            failed.append(version)
            continue
        print(f"[{version}] rebuilding from {commit}", flush=True)
        worktree = prepare(version, commit, root)
        if args.mode == "build":
            command = [sys.executable, "-m", "mkdocs", "build", "-q", "-d", str((args.out / version).resolve())]
        else:
            command = [sys.executable, "-m", "mike", "deploy", "--ignore-remote-status", version]
        result = subprocess.run(command, cwd=worktree, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stderr[-2000:])
            failed.append(version)
        if not args.keep:
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree)], cwd=REPO, check=False)

    if args.mode == "build":
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "versions.json").write_text(json.dumps(published))
    if failed:
        print("Failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
