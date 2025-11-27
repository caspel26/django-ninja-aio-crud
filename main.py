from __future__ import annotations
import subprocess
import re
from datetime import datetime
from html import escape
import json
import urllib.request
import os
from markdown import markdown
import ssl

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
REPO_SLUG = "caspel26/django-ninja-aio-crud"
_RELEASES_CACHE = None


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def _fetch_all_releases() -> dict[str, str]:
    """
    Fetch all GitHub releases once and return a dict {tag_name: body}.
    """
    url = f"https://api.github.com/repos/{REPO_SLUG}/releases"
    req = urllib.request.Request(url)

    token = os.environ.get("GITHUB_TOKEN")
    ssl_context = ssl._create_unverified_context()
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, context=ssl_context) as response:
            data = json.loads(response.read().decode())
            return {
                release["tag_name"]: release.get("body", "").strip() for release in data
            }
    except Exception as e:
        print("Failed to fetch GitHub releases:", e)
        return {}


def _get_release_notes(tag: str) -> str:
    global _RELEASES_CACHE
    if _RELEASES_CACHE is None:
        _RELEASES_CACHE = _fetch_all_releases()
    return _RELEASES_CACHE.get(tag, "")



def _get_tags() -> list[str]:
    raw = _run(["git", "tag", "--list"])
    tags = [t for t in raw.splitlines() if t]
    semver_tags = [t for t in tags if SEMVER_RE.match(t)]

    def sort_key(t: str):
        m = SEMVER_RE.match(t)
        if not m:
            return (0, 0, 0)
        return tuple(int(x) for x in m.groups())

    semver_tags.sort(key=sort_key, reverse=True)  # newest first
    return semver_tags


def _tag_date(tag: str) -> str:
    lines = _run(["git", "show", "-s", "--format=%aI", tag]).splitlines()
    return lines[-1] if lines else ""


_CONV_PREFIX = re.compile(
    r"^(feat|fix|docs|refactor|perf|test|build|ci|chore)(\([^)]*\))?:\s*"
)


def _commit_messages(tag: str, previous: str | None) -> list[str]:
    rev_range = f"{previous}..{tag}" if previous else tag
    log = _run(["git", "log", rev_range, "--pretty=%s", "--no-merges"])
    return [string.strip() for string in log.splitlines() if string.strip()]


def _classify(msgs: list[str]):
    feat, fix, other = [], [], []
    for m in msgs:
        prefix = _CONV_PREFIX.match(m)
        clean = _CONV_PREFIX.sub("", m)
        if not prefix:
            other.append(clean)
        else:
            kind = prefix.group(1)
            if kind == "feat":
                feat.append(clean)
            elif kind == "fix":
                fix.append(clean)
            else:
                other.append(clean)
    return feat, fix, other


def _normalize_version(tag: str) -> str:
    return tag


def _fmt_date_iso(date_iso: str) -> str:
    return (
        datetime.fromisoformat(date_iso.replace("Z", "+00:00")).date().isoformat()
        if date_iso
        else ""
    )


def generate_release_table() -> str:
    tags = _get_tags()
    if not tags:
        return '<div style="font-style:italic;">No git tags found. Create one with <code>git tag -a v0.1.0 -m "Release v0.1.0" && git push --tags</code>.</div>'

    def badge(label: str, count: int, color: str):
        if count == 0:
            return ""
        return (
            f'<img alt="{label}" '
            f'src="https://img.shields.io/badge/{label}-{count}-{color}?style=flat" '
            f'style="margin-right:6px;vertical-align:middle;height:20px;" />'
        )

    def li(items):
        return "".join(f"<li>{escape(i)}</li>" for i in items) or "<li>None</li>"

    rows_html: list[str] = []
    for i, tag in enumerate(tags):
        prev = tags[i + 1] if i + 1 < len(tags) else None
        date_fmt = _fmt_date_iso(_tag_date(tag))
        notes = _get_release_notes(tag)
        notes_html = markdown(notes) if notes else "<p>No release notes.</p>"
        version_dir = _normalize_version(tag)
        doc_link = f"/{version_dir}/"
        diff_link = (
            f"https://github.com/{REPO_SLUG}/compare/{prev}...{tag}"
            if prev
            else f"https://github.com/{REPO_SLUG}/tree/{tag}"
        )
        summary_badges = (
            "<img alt='notes' "
            "src='https://img.shields.io/badge/notes-available-blue?style=flat' "
            "style='margin-right:6px;vertical-align:middle;height:20px;' />"
            if notes
            else "<span style='opacity:.6;'>-</span>"
        )

        details_html = (
            "<details style='margin-top:.45rem;font-size:.7rem;'>"
            "<summary style='cursor:pointer;'>Release notes</summary>"
            f"<div style='margin-top:.5rem;'>{notes_html}</div>"
            "</details>"
        )

        rows_html.append(
            "<tr>"
            f"<td style='padding:.75rem 1rem;vertical-align:top;font-size:.85rem;'>"
            f"<a href='{doc_link}'><strong>{escape(tag)}</strong></a>"
            f"<br/><small><a href='{diff_link}'>diff</a></small>"
            "</td>"
            f"<td style='padding:.75rem 1rem;vertical-align:top;font-size:.8rem;'>{date_fmt}</td>"
            f"<td style='padding:.75rem 1rem;vertical-align:top;font-size:.75rem;line-height:1.25;'>"
            f"{summary_badges}{details_html}"
            "</td>"
            "</tr>"
        )

    html = (
        "<div style='width:100%;overflow-x:auto;'>"
        "<table style='width:100%;min-width:900px;border-collapse:collapse;table-layout:auto;font-size:.8rem;'>"
        "<thead style='background:transparent;'>"
        "<tr>"
        "<th style='text-align:left;padding:.75rem 1rem;border-bottom:2px solid #ccc;width:15%;font-size:.85rem;'>Version</th>"
        "<th style='text-align:left;padding:.75rem 1rem;border-bottom:2px solid #ccc;width:15%;font-size:.85rem;'>Date</th>"
        "<th style='text-align:left;padding:.75rem 1rem;border-bottom:2px solid #ccc;width:70%;font-size:.85rem;'>Summary</th>"
        "</tr>"
        "</thead>"
        "<tbody>" + "".join(rows_html) + "</tbody></table></div>"
    )
    return html


def generate_full_changelog() -> str:
    # NEWEST → OLDEST (removed reversal)
    tags = _get_tags()
    if not tags:
        return "No versions yet."
    out: list[str] = []
    for i, tag in enumerate(tags):
        notes = _get_release_notes(tag)
        date_fmt = _fmt_date_iso(_tag_date(tag))
        out.append(f"## {tag} ({date_fmt})\n")
        out.append(notes or "_No release notes for this release._")
        out.append("\n---\n")
    return "\n".join(out)


def generate_release_cards() -> str:
    # Optional alternative: card layout
    tags = _get_tags()
    if not tags:
        return "<p>No versions yet.</p>"
    parts = [
        '<div class="release-cards" style="display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));">'
    ]
    for i, tag in enumerate(tags):
        prev = tags[i + 1] if i + 1 < len(tags) else None
        notes = _get_release_notes(tag)
        notes_html = markdown(notes) if notes else "<p>No release notes.</p>"
        date_fmt = _fmt_date_iso(_tag_date(tag))
        diff_link = (
            f"https://github.com/{REPO_SLUG}/compare/{prev}...{tag}"
            if prev
            else f"https://github.com/{REPO_SLUG}/tree/{tag}"
        )
        version_dir = _normalize_version(tag)
        parts.append(
            f"""
<div class="release-card" style="border:1px solid #ddd;border-radius:6px;padding:0.75rem;">
  <h4 style="margin:0 0 .25rem;"><a href="/{version_dir}/">{escape(tag)}</a></h4>
  <div style="font-size:.8rem;color:#666;margin-bottom:.5rem;">{date_fmt} · <a href="{diff_link}">diff</a></div>
<details style="font-size:.75rem;">
  <summary>Release notes</summary>
  <div style="padding-left:1rem;margin:.25rem 0;">
    {notes_html}
  </div>
</details>
</div>
""".strip()
        )
    parts.append("</div>")
    return "\n".join(parts)


def define_env(env):
    env.variables["has_release_tags"] = bool(_get_tags())
    env.macros["generate_release_table"] = generate_release_table
    env.macros["generate_full_changelog"] = generate_full_changelog
    env.macros["generate_release_cards"] = generate_release_cards
