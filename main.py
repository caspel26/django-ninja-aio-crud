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


def _tag_anchor(tag: str) -> str:
    """Convert a tag like 'v1.2.3' to a URL-safe anchor ID."""
    return re.sub(r"[^a-zA-Z0-9-]", "", tag.replace(".", "-"))


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

    # Build custom dropdown items
    items: list[str] = []
    first_tag = tags[0]
    first_date = _fmt_date_human(_tag_date(first_tag))
    first_label = f"{first_tag}  —  {first_date}" if first_date else first_tag

    for i, tag in enumerate(tags):
        date_fmt = _fmt_date_human(_tag_date(tag))
        active_cls = " release-dropdown-item--active" if i == 0 else ""
        latest_pill = (
            '<span class="release-dropdown-latest">Latest</span>' if i == 0 else ""
        )
        items.append(
            f'<button class="release-dropdown-item{active_cls}" '
            f'data-value="{_tag_anchor(tag)}" type="button">'
            f'<span class="release-dropdown-item-tag">{escape(tag)}</span>'
            f"{latest_pill}"
            f'<span class="release-dropdown-item-date">{date_fmt}</span>'
            f"</button>"
        )

    selector = (
        '<div class="release-selector">'
        '<label class="release-selector-label">Select version</label>'
        '<div class="release-dropdown" id="release-dropdown">'
        '<button class="release-dropdown-toggle" id="release-toggle" type="button">'
        f'<span class="release-dropdown-toggle-text">{escape(first_label)}</span>'
        '<svg class="release-dropdown-chevron" viewBox="0 0 24 24" width="18" height="18">'
        '<path fill="currentColor" d="M7 10l5 5 5-5z"/>'
        "</svg>"
        "</button>"
        '<div class="release-dropdown-menu" id="release-menu">'
        + "".join(items)
        + "</div>"
        "</div>"
        "</div>"
    )

    # Build hidden cards (only first visible)
    cards: list[str] = []
    for i, tag in enumerate(tags):
        prev = tags[i + 1] if i + 1 < len(tags) else None
        anchor = _tag_anchor(tag)
        date_fmt = _fmt_date_human(_tag_date(tag))
        notes = _get_release_notes(tag)
        notes_html = markdown(notes) if notes else ""
        diff_link = (
            f"https://github.com/{REPO_SLUG}/compare/{prev}...{tag}"
            if prev
            else f"https://github.com/{REPO_SLUG}/tree/{tag}"
        )
        gh_release_link = f"https://github.com/{REPO_SLUG}/releases/tag/{tag}"

        is_latest = i == 0
        latest_badge = (
            ' <span class="release-badge release-badge--latest">Latest</span>'
            if is_latest
            else ""
        )
        latest_cls = " release-card--latest" if is_latest else ""
        hidden = "" if is_latest else ' style="display:none"'

        if notes_html:
            body = f'<div class="release-card-body">{notes_html}</div>'
        else:
            body = (
                '<div class="release-card-body">'
                '<p class="release-notes-empty">'
                "No release notes for this version."
                "</p></div>"
            )

        cards.append(
            f'<div class="release-card{latest_cls}" data-version="{anchor}"{hidden}>'
            f'<div class="release-card-header">'
            f"<h4>"
            f'<a href="{gh_release_link}">{escape(tag)}</a>'
            f"{latest_badge}"
            f"</h4>"
            f'<span class="release-card-date">{date_fmt}</span>'
            f"</div>"
            f"{body}"
            f'<div class="release-card-footer">'
            f'<a href="{gh_release_link}">GitHub Release</a>'
            f' · <a href="{diff_link}">Diff</a>'
            f"</div>"
            f"</div>"
        )

    cards_container = (
        '<div class="release-display">' + "\n".join(cards) + "</div>"
    )

    script = (
        "<script>"
        "(function(){"
        "var dd=document.getElementById('release-dropdown'),"
        "toggle=document.getElementById('release-toggle'),"
        "menu=document.getElementById('release-menu'),"
        "text=toggle.querySelector('.release-dropdown-toggle-text');"
        "toggle.addEventListener('click',function(e){"
        "e.stopPropagation();"
        "dd.classList.toggle('release-dropdown--open');"
        "if(dd.classList.contains('release-dropdown--open')){"
        "var active=menu.querySelector('.release-dropdown-item--active');"
        "if(active)active.scrollIntoView({block:'nearest'});"
        "}"
        "});"
        "menu.addEventListener('click',function(e){"
        "var btn=e.target.closest('.release-dropdown-item');"
        "if(!btn)return;"
        "var v=btn.getAttribute('data-value');"
        "menu.querySelectorAll('.release-dropdown-item').forEach(function(b){"
        "b.classList.remove('release-dropdown-item--active');"
        "});"
        "btn.classList.add('release-dropdown-item--active');"
        "var tag=btn.querySelector('.release-dropdown-item-tag').textContent,"
        "date=btn.querySelector('.release-dropdown-item-date').textContent;"
        "text.textContent=date?tag+'  —  '+date:tag;"
        "dd.classList.remove('release-dropdown--open');"
        "document.querySelectorAll('.release-display .release-card')"
        ".forEach(function(c){"
        "c.style.display=c.getAttribute('data-version')===v?'':'none';"
        "});"
        "});"
        "document.addEventListener('click',function(){"
        "dd.classList.remove('release-dropdown--open');"
        "});"
        "})();"
        "</script>"
    )

    return selector + cards_container + script


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
