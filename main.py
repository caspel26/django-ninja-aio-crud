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


def _fmt_date_human(date_iso: str) -> str:
    """Format date as 'Jan 15, 2025' style."""
    if not date_iso:
        return ""
    try:
        dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00")).date()
        return dt.strftime("%b %d, %Y")
    except Exception:
        return date_iso


def generate_release_table() -> str:
    tags = _get_tags()
    if not tags:
        return (
            '<div class="admonition info">'
            '<p class="admonition-title">No Releases Yet</p>'
            "<p>No git tags found. Create one with:</p>"
            "<pre><code>git tag -a v0.1.0 -m &quot;Release v0.1.0&quot; &amp;&amp; git push --tags</code></pre>"
            "</div>"
        )

    cards_html: list[str] = []
    for i, tag in enumerate(tags):
        prev = tags[i + 1] if i + 1 < len(tags) else None
        date_raw = _tag_date(tag)
        date_fmt = _fmt_date_human(date_raw)
        notes = _get_release_notes(tag)
        notes_html = markdown(notes) if notes else ""
        diff_link = (
            f"https://github.com/{REPO_SLUG}/compare/{prev}...{tag}"
            if prev
            else f"https://github.com/{REPO_SLUG}/tree/{tag}"
        )
        gh_release_link = f"https://github.com/{REPO_SLUG}/releases/tag/{tag}"

        # Determine if this is the latest release
        is_latest = i == 0
        latest_badge = (
            '<span class="release-badge release-badge--latest">Latest</span>'
            if is_latest
            else ""
        )

        # Build notes section
        if notes_html:
            notes_section = (
                '<div class="release-notes-content">'
                f"{notes_html}"
                "</div>"
            )
        else:
            notes_section = (
                '<div class="release-notes-empty">'
                "No release notes for this version."
                "</div>"
            )

        cards_html.append(
            f'<div class="release-entry{"  release-entry--latest" if is_latest else ""}">'
            f'<div class="release-header">'
            f'<div class="release-version">'
            f'<span class="release-tag">{escape(tag)}</span>'
            f"{latest_badge}"
            f"</div>"
            f'<div class="release-meta">'
            f'<span class="release-date">{date_fmt}</span>'
            f'<span class="release-links">'
            f'<a href="{gh_release_link}" title="GitHub Release">GitHub</a>'
            f' · <a href="{diff_link}" title="View diff">Diff</a>'
            f"</span>"
            f"</div>"
            f"</div>"
            f"{notes_section}"
            f"</div>"
        )

    html = (
        '<div class="release-timeline">'
        + "".join(cards_html)
        + "</div>"
    )
    return html


def generate_full_changelog() -> str:
    # NEWEST -> OLDEST (removed reversal)
    tags = _get_tags()
    if not tags:
        return "No versions yet."
    out: list[str] = []
    for tag in tags:
        notes = _get_release_notes(tag)
        date_fmt = _fmt_date_human(_tag_date(tag))
        out.append(f"## {tag} ({date_fmt})\n")
        out.append(notes or "_No release notes for this release._")
        out.append("\n---\n")
    return "\n".join(out)


def generate_release_cards() -> str:
    tags = _get_tags()
    if not tags:
        return (
            '<div class="admonition info">'
            '<p class="admonition-title">No Releases Yet</p>'
            "<p>No versions have been tagged yet.</p>"
            "</div>"
        )
    parts = ['<div class="release-grid">']
    for i, tag in enumerate(tags):
        prev = tags[i + 1] if i + 1 < len(tags) else None
        notes = _get_release_notes(tag)
        notes_html = markdown(notes) if notes else "<p>No release notes.</p>"
        date_fmt = _fmt_date_human(_tag_date(tag))
        diff_link = (
            f"https://github.com/{REPO_SLUG}/compare/{prev}...{tag}"
            if prev
            else f"https://github.com/{REPO_SLUG}/tree/{tag}"
        )
        gh_release_link = f"https://github.com/{REPO_SLUG}/releases/tag/{tag}"
        is_latest = i == 0
        latest_cls = " release-card--latest" if is_latest else ""
        latest_badge = (
            '<span class="release-badge release-badge--latest">Latest</span>'
            if is_latest
            else ""
        )
        parts.append(
            f'<div class="release-card{latest_cls}">'
            f'<div class="release-card-header">'
            f'<h4><a href="{gh_release_link}">{escape(tag)}</a>{latest_badge}</h4>'
            f'<span class="release-card-date">{date_fmt}</span>'
            f"</div>"
            f'<div class="release-card-body">{notes_html}</div>'
            f'<div class="release-card-footer">'
            f'<a href="{gh_release_link}">Release</a>'
            f' · <a href="{diff_link}">Diff</a>'
            f"</div>"
            f"</div>"
        )
    parts.append("</div>")
    return "\n".join(parts)


def define_env(env):
    env.variables["has_release_tags"] = bool(_get_tags())
    env.macros["generate_release_table"] = generate_release_table
    env.macros["generate_full_changelog"] = generate_full_changelog
    env.macros["generate_release_cards"] = generate_release_cards
