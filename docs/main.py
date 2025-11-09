from __future__ import annotations
import subprocess
import re
from datetime import datetime
from html import escape

SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
REPO_SLUG = "caspel26/django-ninja-aio-crud"


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


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

    EMOJI = {"feat": "✨", "fix": "🐛", "other": "📦"}

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
        msgs = _commit_messages(tag, prev)
        feat, fix, other = _classify(msgs)
        version_dir = _normalize_version(tag)
        doc_link = f"/{version_dir}/"
        diff_link = (
            f"https://github.com/{REPO_SLUG}/compare/{prev}...{tag}"
            if prev
            else f"https://github.com/{REPO_SLUG}/tree/{tag}"
        )
        summary_badges = (
            badge("feat", len(feat), "brightgreen")
            + badge("fix", len(fix), "orange")
            + badge("other", len(other), "blue")
        ) or "<span style='opacity:.6;'>-</span>"

        details_html = (
            "<details style='margin-top:.45rem;font-size:.7rem;'>"
            "<summary style='cursor:pointer;'>Details</summary>"
            "<div style='display:grid;grid-template-columns:auto 1fr;row-gap:.25rem;column-gap:.5rem;"
            "margin:.45rem 0 .2rem;'>"
            f"<div><strong>Features {EMOJI['feat']}</strong></div><ul style='margin:0;padding-left:1rem;'>{li(feat)}</ul>"
            f"<div><strong>Fixes {EMOJI['fix']}</strong></div><ul style='margin:0;padding-left:1rem;'>{li(fix)}</ul>"
            f"<div><strong>Other {EMOJI['other']}</strong></div><ul style='margin:0;padding-left:1rem;'>{li(other)}</ul>"
            "</div></details>"
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
        "<tbody>"
        + "".join(rows_html)
        + "</tbody></table></div>"
    )
    return html


def generate_full_changelog() -> str:
    # NEWEST → OLDEST (removed reversal)
    tags = _get_tags()
    if not tags:
        return "No versions yet."
    out: list[str] = []
    for i, tag in enumerate(tags):
        prev = tags[i + 1] if i + 1 < len(tags) else None
        feat, fix, other = _classify(_commit_messages(tag, prev))
        date_fmt = _fmt_date_iso(_tag_date(tag))
        out.append(f"### {tag} ({date_fmt})\n")

        def block(title: str, items: list[str]):
            if not items:
                return f"*No {title.lower()}*\n"
            return "".join(f"- {escape(i)}\n" for i in items)

        if feat:
            out.append("#### Features\n" + block("Features", feat) + "\n")
        if fix:
            out.append("#### Fixes\n" + block("Fixes", fix) + "\n")
        rem_other = [m for m in other if not _CONV_PREFIX.match(m)]
        if rem_other:
            out.append("#### Other\n" + block("Other", rem_other) + "\n")
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
        feat, fix, other = _classify(_commit_messages(tag, prev))
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
  <ul style="margin:0 0 .5rem;padding-left:1.2rem;font-size:.85rem;">
    <li><strong>feat:</strong> {len(feat)}</li>
    <li><strong>fix:</strong> {len(fix)}</li>
    <li><strong>other:</strong> {len(other)}</li>
  </ul>
  <details style="font-size:.75rem;">
    <summary>Details</summary>
    <ul style="padding-left:1rem;margin:.25rem 0;">
      {"".join(f"<li>{escape(m)}</li>" for m in (feat + fix + other)) or "<li>None</li>"}
    </ul>
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
