#!/usr/bin/env python3
"""Generate MkDocs-compatible Markdown comparison report.

This creates a Markdown file that can be included in the MkDocs documentation
site, providing framework comparison data with the same theme and styling.
"""

import argparse
import json
import sys
from pathlib import Path


def generate_markdown_report(results_file: Path, output_file: Path) -> None:
    """Generate Markdown comparison report from JSON results."""
    if not results_file.exists():
        print(f"Error: Results file not found: {results_file}", file=sys.stderr)
        sys.exit(1)

    with open(results_file) as f:
        data = json.load(f)

    if "runs" not in data or not data["runs"]:
        print("Error: No comparison runs found in results file", file=sys.stderr)
        sys.exit(1)

    latest_run = data["runs"][-1]
    timestamp = latest_run.get("timestamp", "Unknown")
    python_version = latest_run.get("python_version", "Unknown")
    results = latest_run.get("results", {})

    frameworks = list(results.keys())
    if not frameworks:
        print("Error: No framework results found", file=sys.stderr)
        sys.exit(1)

    operations = list(results[frameworks[0]].keys())

    # Build performance overview table
    table_header = "| Operation | " + " | ".join(f"**{fw}**" for fw in frameworks) + " |"
    table_sep = "|-----------|" + "|".join("---" for _ in frameworks) + "|"
    table_rows = ""
    for op in operations:
        op_title = op.replace("_", " ").title()
        values = []
        for fw in frameworks:
            if op in results[fw]:
                values.append(f"{results[fw][op]['median_ms']:.2f}ms")
            else:
                values.append("N/A")
        table_rows += f"| **{op_title}** | " + " | ".join(values) + " |\n"

    md = f"""# Framework Comparison

!!! info "Test Environment"
    - **Tested on:** {timestamp}
    - **Python:** {python_version}
    - **Compared:** {', '.join(frameworks)}
    - **Operations:** {len(operations)} (CRUD + complex async relations)

## The Honest Truth About Performance

Let's be direct: **django-ninja-aio-crud is NOT the fastest framework for simple CRUD operations**.

Frameworks like FastAPI and pure Django Ninja may show better raw performance on basic operations. This is an intentional trade-off.

### What You Trade Speed For

django-ninja-aio-crud sacrifices marginal performance for **massive developer productivity gains** on complex async Django projects - particularly when dealing with relations.

---

## Code Complexity Comparison

This is where django-ninja-aio-crud truly differentiates itself. Let's compare **real implementation code** for the same feature across frameworks.

### Task: CRUD API with Reverse FK Relations

#### django-ninja-aio-crud

```python
from django.db import models
from ninja_aio.models import ModelSerializer
from ninja_aio import NinjaAIO
from ninja_aio.views import APIViewSet


class Author(ModelSerializer):
    name = models.CharField(max_length=200)
    email = models.EmailField()

    class CreateSerializer:
        fields = ["name", "email"]

    class ReadSerializer:
        fields = ["id", "name", "email", "books"]  # Reverse FK: automatic!

    class UpdateSerializer:
        optionals = [("name", str), ("email", str)]


api = NinjaAIO()


@api.viewset(model=Author)
class AuthorViewSet(APIViewSet):
    pass  # All CRUD endpoints auto-generated
```

**What you get automatically:**

- All CRUD endpoints (create, list, retrieve, update, delete)
- Reverse FK serialization with proper async handling
- Automatic `prefetch_related` optimization
- Type-safe Pydantic schemas
- Input validation
- Pagination

---

#### FastAPI

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class BookOut(BaseModel):
    id: int
    title: str

    class Config:
        from_attributes = True


class AuthorOut(BaseModel):
    id: int
    name: str
    email: str
    books: list[BookOut]

    class Config:
        from_attributes = True


class AuthorCreate(BaseModel):
    name: str
    email: str


@app.post("/authors/")
async def create_author(data: AuthorCreate):
    author = await Author.objects.acreate(**data.dict())
    return {{"id": author.id, "name": author.name, "email": author.email}}


@app.get("/authors/")
async def list_authors():
    authors = []
    async for author in Author.objects.all():
        authors.append(AuthorOut.model_validate(author))
    return authors


@app.get("/authors/{{author_id}}")
async def get_author(author_id: int):
    author = await Author.objects.prefetch_related("books").aget(pk=author_id)

    # Must manually iterate reverse FK in async
    books = []
    async for book in author.books.all():
        books.append(BookOut.model_validate(book))

    return {{
        "id": author.id,
        "name": author.name,
        "email": author.email,
        "books": [b.dict() for b in books],
    }}


@app.patch("/authors/{{author_id}}")
async def update_author(author_id: int, data: AuthorCreate):
    author = await Author.objects.aget(pk=author_id)
    for field, value in data.dict(exclude_unset=True).items():
        setattr(author, field, value)
    await author.asave()
    return AuthorOut.model_validate(author)


@app.delete("/authors/{{author_id}}")
async def delete_author(author_id: int):
    author = await Author.objects.aget(pk=author_id)
    await author.adelete()
    return {{"deleted": True}}


# Still missing: list pagination, filtering, proper error handling
```

---

#### ADRF (Async Django REST Framework)

```python
from adrf.serializers import ModelSerializer as AsyncModelSerializer
from adrf.viewsets import ModelViewSet as AsyncModelViewSet
from rest_framework.routers import DefaultRouter


class BookSerializer(AsyncModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "title"]


class AuthorSerializer(AsyncModelSerializer):
    books = BookSerializer(many=True, read_only=True)

    class Meta:
        model = Author
        fields = ["id", "name", "email", "books"]


class AuthorCreateSerializer(AsyncModelSerializer):
    class Meta:
        model = Author
        fields = ["name", "email"]


class AuthorViewSet(AsyncModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return AuthorCreateSerializer
        return AuthorSerializer

    def get_queryset(self):
        return Author.objects.prefetch_related("books")


router = DefaultRouter()
router.register(r"authors", AuthorViewSet)
```

---

### The Verdict

| Framework | Lines of Code | Reverse FK Handling | Auto Prefetch | CRUD Automation |
|-----------|---------------|---------------------|---------------|-----------------|
| **django-ninja-aio-crud** | **~20** | Automatic | Yes | Full |
| **FastAPI** | ~80+ | Manual async iteration | No | None |
| **ADRF** | ~45+ | Needs serializer config | Manual | Partial |

### When THIS Framework Makes Sense

**Choose django-ninja-aio-crud when:**

- You have **complex data models** with relations
- You need **async Django** with proper ORM handling
- **Developer time** matters more than marginal performance gains
- You value **type safety** and **maintainability**

**Choose simpler frameworks when:**

- You have **flat, simple data models**
- Every **millisecond** counts more than dev time
- You prefer **full manual control** over automation

---

## Performance Results

{table_header}
{table_sep}
{table_rows}

!!! note "Understanding the Numbers"
    Lower is better. All frameworks use the same Django models and database.
    A 10-20% performance difference is negligible compared to hours of development time saved on complex async relations.

---

## Live Comparison Report

The latest framework comparison benchmarks from the `main` branch are automatically published as an interactive HTML report:

<div class="cta-buttons" markdown>

[View Live Comparison Report :material-chart-box-outline:](https://caspel26.github.io/django-ninja-aio-crud/comparison/comparison_report.html){{ .md-button .md-button--primary target="_blank" }}

</div>

---

## Methodology

All frameworks were tested under identical conditions:

- **Same Django models and database** (SQLite in-memory)
- **Same operations** performed by each framework
- **Async where possible** (sync frameworks wrapped with `sync_to_async`)
- **Multiple iterations** per operation for statistical reliability

---
"""

    output_file.write_text(md)
    print(f"Markdown report generated: {output_file}")


def main():
    """Parse arguments and generate report."""
    parser = argparse.ArgumentParser(
        description="Generate MkDocs Markdown comparison report"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).parent.parent.parent / "comparison_results.json",
        help="Path to comparison results JSON file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent.parent.parent / "docs" / "comparison.md",
        help="Path to output Markdown file",
    )

    args = parser.parse_args()
    generate_markdown_report(args.input, args.output)


if __name__ == "__main__":
    main()
