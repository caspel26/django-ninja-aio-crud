"""Build the home page of a rebuilt 1.x/2.x version from docs-legacy/legacy_home.html.

The page has the same sections as the v3 home. Code, feature cards,
benchmarks and links are picked from what the version actually ships.
"""

import pathlib
import re
from html import escape

HERE = pathlib.Path(__file__).resolve().parent

ICONS = {
    "bolt": '<path d="M13 3L5 14h6l-1 7 8-11h-6z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    "graph": '<circle cx="6" cy="6" r="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="18" cy="12" r="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="6" cy="18" r="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M8.3 7.2l7.4 3.6M8.3 16.8l7.4-3.6" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "filter": '<path d="M4 5h16l-6 7v6l-4 2v-8z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    "lock": '<rect x="5" y="10" width="14" height="10" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M8 10V7a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "hook": '<path d="M12 3v5M12 16v5M3 12h5M16 12h5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/><circle cx="12" cy="12" r="3" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "layers": '<path d="M12 3l9 5-9 5-9-5z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="M3 13l9 5 9-5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    "stack": '<rect x="4" y="4" width="16" height="4" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="4" y="10" width="16" height="4" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.7"/><rect x="4" y="16" width="16" height="4" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "trash": '<path d="M5 7h14M10 7V5h4v2M7 7l1 13h8l1-13" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>',
    "admin": '<rect x="3" y="4" width="18" height="16" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.7"/><path d="M3 9h18M8 9v11" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    "robot": '<rect x="4" y="6" width="16" height="12" rx="3" fill="none" stroke="currentColor" stroke-width="1.7"/><circle cx="9.5" cy="12" r="1.3" fill="currentColor"/><circle cx="14.5" cy="12" r="1.3" fill="currentColor"/><path d="M12 3v3" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    "action": '<path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
}

API_DECORATOR = """<span class="k">from</span> ninja_aio <span class="k">import</span> NinjaAIO
<span class="k">from</span> ninja_aio.views <span class="k">import</span> APIViewSet
<span class="k">from</span> .models <span class="k">import</span> Article

api <span class="o">=</span> <span class="f">NinjaAIO</span>(title<span class="o">=</span><span class="s">"Blog API"</span>)


<span class="d">@api.viewset</span>(Article)
<span class="k">class</span> <span class="f">ArticleViewSet</span>(APIViewSet):
    <span class="k">pass</span>"""

API_CLASSIC = """<span class="k">from</span> ninja_aio <span class="k">import</span> NinjaAIO
<span class="k">from</span> ninja_aio.views <span class="k">import</span> APIViewSet
<span class="k">from</span> .models <span class="k">import</span> Article

api <span class="o">=</span> <span class="f">NinjaAIO</span>(title<span class="o">=</span><span class="s">"Blog API"</span>)


<span class="k">class</span> <span class="f">ArticleViewSet</span>(APIViewSet):
    model <span class="o">=</span> Article
    api <span class="o">=</span> api


<span class="f">ArticleViewSet</span>().<span class="f">add_views_to_route</span>()"""

ACTION_CODE = """<pre class="nac-card__code"><code><span class="d">@action</span>(detail<span class="o">=</span><span class="b">True</span>, methods<span class="o">=</span>[<span class="s">"post"</span>])
<span class="k">async def</span> <span class="f">publish</span>(self, request, pk): ...</code></pre>"""


def _contains(worktree: pathlib.Path, pattern: str, path: str = "ninja_aio") -> bool:
    regex = re.compile(pattern)
    root = worktree / path
    files = [root] if root.is_file() else root.rglob("*.py")
    return any(regex.search(f.read_text(errors="ignore")) for f in files if f.is_file())


def detect_features(worktree: pathlib.Path) -> set[str]:
    checks = {
        "viewset_decorator": (r"def viewset\(", "ninja_aio/api.py"),
        "serializer": (r"class Serializer\(", "ninja_aio"),
        "action": (r"def action\(", "ninja_aio"),
        "on": (r"def on\(", "ninja_aio"),
        "bulk": (r"_bulk_views|def bulk_create", "ninja_aio/views"),
        "soft_delete": (r"SoftDelete", "ninja_aio"),
        "admin": (r"def register_admin|class \w*Admin", "ninja_aio/admin.py"),
        "mcp": (r".", "ninja_aio/mcp/__init__.py"),
    }
    found = {"async", "relations", "filters", "jwt", "hooks"}
    for name, (pattern, path) in checks.items():
        if (worktree / path).exists() and _contains(worktree, pattern, path):
            found.add(name)
    return found


def _cards(features: set[str]) -> list[dict]:
    cards = [
        {"key": "async", "icon": "bolt", "wide": True, "title": "Fully async",
         "text": "Queries, validation and serialization run on Django's async ORM, end to end."},
        {"key": "relations", "icon": "graph", "title": "Relations",
         "text": "Nested reads for foreign keys, reverse relations and many-to-many endpoints."},
        {"key": "filters", "icon": "filter", "title": "Filters and pagination",
         "text": "Typed query parameters and paginated lists."},
        {"key": "jwt", "icon": "lock", "title": "JWT authentication",
         "text": "Async JWT bearer auth, per viewset or per operation."},
        {"key": "hooks", "icon": "hook", "title": "Lifecycle hooks",
         "text": "Run code before and after create, update and delete."},
        {"key": "serializer", "icon": "layers", "title": "Plain Django models",
         "text": "Keep your models as they are and describe schemas in a Serializer."},
        {"key": "bulk", "icon": "stack", "title": "Bulk operations",
         "text": "Create, update and delete many objects in one request."},
        {"key": "soft_delete", "icon": "trash", "title": "Soft delete",
         "text": "Hide deleted rows and restore them later."},
        {"key": "admin", "icon": "admin", "title": "Auto admin",
         "text": "Register the Django admin straight from your serializer."},
        {"key": "mcp", "icon": "robot", "title": "MCP server",
         "text": "Expose your viewsets as tools for AI agents."},
    ]
    chosen = [c for c in cards if c["key"] in features]
    if "action" in features:
        text = "Add endpoints next to CRUD with <code>@action</code>"
        text += " and <code>@on</code>." if "on" in features else "."
        chosen.append({"key": "action", "icon": "action", "wide": True, "title": "Custom actions",
                       "text": text, "code": ACTION_CODE})

    # Fill the 3-column grid without holes.
    slots = sum(2 if c.get("wide") else 1 for c in chosen)
    if slots % 3 == 1:
        chosen[0]["wide"] = False
    elif slots % 3 == 2:
        narrow = [c for c in chosen if not c.get("wide")]
        if narrow:
            narrow[-1]["wide"] = True
    return chosen


def _card_html(card: dict) -> str:
    wide = " nac-card--wide" if card.get("wide") else ""
    text = card["text"] if "<code>" in card["text"] else escape(card["text"])
    return (
        f'        <div class="nac-card{wide}" data-reveal data-spotlight>\n'
        f'          <span class="nac-card__icon" aria-hidden="true"><svg viewBox="0 0 24 24">{ICONS[card["icon"]]}</svg></span>\n'
        f'          <h3>{escape(card["title"])}</h3>\n'
        f"          <p>{text}</p>\n"
        f'{card.get("code", "")}'
        "        </div>"
    )


def _benchmarks(worktree: pathlib.Path) -> str:
    page = worktree / "docs/comparison.md"
    if not page.exists():
        return ""
    text = page.read_text()
    header = re.search(r"^\|\s*Operation\s*\|(.+)$", text, re.M)
    row = re.search(r"^\|\s*List\s*\|(.+)$", text, re.M)
    if not header or not row:
        return ""
    names = [re.sub(r"[*`]", "", n).strip() for n in header.group(1).split("|") if n.strip()]
    values = [re.search(r"[\d.]+", v) for v in row.group(1).split("|") if v.strip()]
    pairs = [(n, float(v.group())) for n, v in zip(names, values) if v]
    if len(pairs) < 2:
        return ""
    top = max(v for _, v in pairs)
    bars = []
    for name, value in pairs:
        own = "aio" in name.lower()
        label = "django-ninja-aio-crud" if own else escape(name)
        width = max(value / top * 100, 1)
        bars.append(
            f'        <div class="nac-bar{" is-self" if own else ""}" role="row"><span role="cell">{label}</span>'
            f'<span class="nac-bar__track" aria-hidden="true"><span style="--w: {width:.1f}%"></span></span>'
            f'<span role="cell">{value:.2f} ms</span></div>'
        )
    return f"""
    <section class="nac-section nac-perf" aria-labelledby="nac-perf-title">
      <div class="nac-perf__copy" data-reveal>
        <p class="nac-eyebrow">Performance</p>
        <h2 id="nac-perf-title">Automation that costs microseconds</h2>
        <p>Median time for the list endpoint, same models and database for every framework.</p>
        <a class="nac-link-arrow" href="{{{{ 'comparison/' | url }}}}">See all benchmarks</a>
      </div>
      <div class="nac-bars" role="table" aria-label="List endpoint, median milliseconds" data-reveal>
{chr(10).join(bars)}
      </div>
    </section>
"""


def _paths(worktree: pathlib.Path) -> str:
    docs = worktree / "docs"
    options = [
        ("getting_started/quick_start.md", "Get going", "Quick start", "One model, five endpoints, running locally."),
        ("tutorial/model.md", "Step by step", "Tutorial", "Build a blog API from the model up."),
        ("api/views/api_view_set.md", "Reference", "APIViewSet", "Every option of the CRUD viewset."),
        ("api/models/model_serializer.md", "Reference", "ModelSerializer", "Schemas, relations and CRUD helpers."),
    ]
    cards = []
    for index, (source, kicker, title, text) in enumerate(o for o in options if (docs / o[0]).exists()):
        url = source.removesuffix(".md") + "/"
        cards.append(
            f'        <a class="nac-path" href="{{{{ \'{url}\' | url }}}}" data-reveal style="--d: {index}">\n'
            f'          <span class="nac-path__kicker">{kicker}</span>\n'
            f"          <h3>{title}</h3>\n"
            f"          <p>{text}</p>\n"
            "        </a>"
        )
    cards = cards[:3]
    cards.append(
        f'        <a class="nac-path" href="{{{{ base_url }}}}/../latest/migration/" data-reveal style="--d: {len(cards)}">\n'
        '          <span class="nac-path__kicker">What\'s new</span>\n'
        "          <h3>Upgrade to 3.0</h3>\n"
        "          <p>Sync and async from one serializer, and more.</p>\n"
        "        </a>"
    )
    return "\n".join(cards)


def render_home(worktree: pathlib.Path) -> str:
    features = detect_features(worktree)
    decorator = "viewset_decorator" in features
    template = (HERE / "legacy_home.html").read_text()
    replacements = {
        "@@API_CODE@@": API_DECORATOR if decorator else API_CLASSIC,
        "@@REGISTER_TEXT@@": (
            "One decorator on a class with no body is enough to start."
            if decorator
            else "Point an APIViewSet at the model and add its routes to the API."
        ),
        "@@CARDS@@": "\n".join(_card_html(c) for c in _cards(features)),
        "@@PERF@@": _benchmarks(worktree),
        "@@PATHS@@": _paths(worktree),
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    return template
