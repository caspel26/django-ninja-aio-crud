"""Read the actual Markdown code blocks; no copied documentation examples."""
from dataclasses import dataclass
from pathlib import Path
import re
import textwrap

ROOT = Path(__file__).resolve().parents[2]
FENCE = re.compile(r"(?m)^([ \t]*)```python[^\n]*\n(.*?)^\1```\s*$", re.S)


@dataclass(frozen=True)
class Example:
    path: Path
    index: int
    code: str

    @property
    def filename(self):
        return f"{self.path.relative_to(ROOT)}:python-block-{self.index + 1}"


def blocks(path):
    path = ROOT / path
    return [Example(path, index, textwrap.dedent(match[2])) for index, match in enumerate(FENCE.finditer(path.read_text()))]


def source(path, index):
    return blocks(path)[index].code
