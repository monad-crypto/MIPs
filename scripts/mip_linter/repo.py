import re
from pathlib import Path

DRAFT_FILE_RE = re.compile(r"^(MIP|MRC)-draft_[A-Za-z0-9_-]+\.md$")
MENTION_RE = re.compile(r"\b(mip|mrc)-(\d+)\b", re.IGNORECASE)
UNDASHED_MENTION_RE = re.compile(r"\b(?:mip|mrc)\s*\d+\b", re.IGNORECASE)


class Repo:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def proposal_path(self, number: int) -> Path | None:
        for kind in ("MIP", "MRC"):
            path = self.root / f"{kind}s" / f"{kind}-{number}.md"
            if path.is_file():
                return path
        return None

    def proposal_kind(self, number: int) -> str | None:
        path = self.proposal_path(number)
        return path.name[:3] if path else None

    def all_proposals(self) -> list[Path]:
        return sorted(path for kind in ("MIPs", "MRCs") for path in (self.root / kind).glob("*.md"))
