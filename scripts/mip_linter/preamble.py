import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install -r scripts/requirements.txt")

from .findings import Report
from .markdown import split_url
from .repo import DRAFT_FILE_RE, UNDASHED_MENTION_RE, Repo

MAX_TITLE_LENGTH = 90
MAX_DESCRIPTION_LENGTH = 140
FORUM_HOST = "forum.monad.xyz"

HEADER_ORDER = [
    "mip",
    "title",
    "description",
    "author",
    "discussions-to",
    "status",
    "last-call-deadline",
    "type",
    "category",
    "created",
    "requires",
    "withdrawal-reason",
]
REQUIRED_HEADERS = [
    "mip",
    "title",
    "description",
    "author",
    "discussions-to",
    "status",
    "type",
    "created",
]
STATUSES = ["Draft", "Review", "Last Call", "Final", "Stagnant", "Withdrawn", "Living"]
CATEGORIES = {
    "Standards Track": ["Core", "Networking", "Interface", "MRC"],
    "Meta": ["Process", "Hardfork"],
    "Informational": [],
}
SMALL_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "as", "at",
    "by", "from", "in", "into", "of", "off", "on", "onto", "out", "over", "per",
    "to", "up", "via", "with", "vs",
}

HEADER_LINE_RE = re.compile(r"^([a-z][a-z0-9-]*):(.*)$")
AUTHOR_RE = re.compile(
    r"^(?:(?P<name>[^()<>@,]+?)"
    r"(?: \((?P<user>@[A-Za-z0-9-]+)\))?"
    r"(?: <(?P<email>[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>)?"
    r"|\((?P<only_user>@[A-Za-z0-9-]+)\))$"
)
STANDARD_RE = re.compile(r"standar", re.IGNORECASE)


@dataclass
class Header:
    line: int
    name: str
    raw: str

    @property
    def value(self) -> str:
        return self.raw.strip()


@dataclass
class Preamble:
    number: int | None = None
    status: str | None = None
    category: str | None = None


def one_of(values: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in values)


def title_case_violations(title: str) -> list[str]:
    words = title.split()
    violations = []
    for i, token in enumerate(words):
        word = token.strip("`\"'()[]{}:;,.!?")
        if not word.isalpha() or not word.islower():
            continue
        if word in SMALL_WORDS and 0 < i < len(words) - 1:
            continue
        violations.append(word)
    return violations


def parse_headers(report: Report, lines: list[str]) -> list[Header]:
    headers = []
    for lineno, line in enumerate(lines, start=2):
        match = HEADER_LINE_RE.match(line)
        if not match:
            report.error(lineno, "preamble-header", "preamble lines must be `name: value` headers")
            continue
        headers.append(Header(lineno, match.group(1), match.group(2)))
    return headers


def check_preamble(report: Report, lines: list[str], path: Path, repo: Repo) -> Preamble:
    preamble = Preamble()
    by_name: dict[str, Header] = {}
    last_index = -1
    for header in parse_headers(report, lines):
        if header.name in by_name:
            report.error(header.line, "preamble-no-dup", f"preamble header `{header.name}` appears more than once")
            continue
        by_name[header.name] = header
        if header.name not in HEADER_ORDER:
            report.error(header.line, "preamble-unknown", f"`{header.name}` is not a MIP preamble header")
            continue
        index = HEADER_ORDER.index(header.name)
        if index < last_index:
            report.error(
                header.line,
                "preamble-order",
                f"preamble header `{header.name}` is out of order; the order is {', '.join(HEADER_ORDER)}",
            )
        last_index = max(last_index, index)
        if header.raw != (f" {header.value}" if header.value else ""):
            report.error(
                header.line,
                "preamble-trim",
                f"preamble header `{header.name}` must be followed by one space and have no trailing whitespace",
            )
    check_yaml(report, lines, by_name)

    is_draft_file = DRAFT_FILE_RE.match(path.name) is not None
    for name in REQUIRED_HEADERS:
        if name not in by_name and not (name == "mip" and is_draft_file):
            report.error(1, "preamble-req", f"preamble header `{name}` is required")

    mip = by_name.get("mip")
    if mip:
        if re.fullmatch(r"[1-9][0-9]*", mip.value):
            preamble.number = int(mip.value)
        else:
            report.error(mip.line, "preamble-uint", "preamble header `mip` must be a positive integer")

    check_title(report, by_name.get("title"), preamble.number)
    check_description(report, by_name.get("description"), preamble.number)
    check_author(report, by_name.get("author"))
    check_discussions_to(report, by_name.get("discussions-to"))

    status = by_name.get("status")
    if status:
        if status.value in STATUSES:
            preamble.status = status.value
        else:
            report.error(status.line, "preamble-enum", f"`status` must be one of {one_of(STATUSES)}")

    preamble.category = check_type_and_category(report, by_name.get("type"), by_name.get("category"))
    check_date(report, by_name.get("created"))
    check_date(report, by_name.get("last-call-deadline"))
    if preamble.status == "Last Call" and "last-call-deadline" not in by_name:
        report.error(status.line, "preamble-req-last-call-deadline", "`Last Call` MIPs must have a `last-call-deadline` header")
    if preamble.status == "Withdrawn" and "withdrawal-reason" not in by_name:
        report.error(status.line, "preamble-req-withdrawal-reason", "`Withdrawn` MIPs must have a `withdrawal-reason` header")
    check_requires(report, by_name.get("requires"), repo)
    if preamble.category == "Hardfork" and "requires" not in by_name:
        report.error(by_name["category"].line, "preamble-req-requires", "`Hardfork` MIPs must list the included MIPs in `requires`")
    check_file_name(report, path, repo, preamble, is_draft_file)
    return preamble


def check_yaml(report: Report, lines: list[str], by_name: dict[str, Header]) -> None:
    text = "\n".join(lines)
    try:
        parsed = yaml.safe_load(text)
    except (yaml.YAMLError, RecursionError) as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 2 if mark else 2
        problem = " ".join(str(exc).split())
        report.error(line, "preamble-yaml", f"the preamble is not valid YAML, so Jekyll cannot render the page: {problem}")
        return
    except ValueError:
        # Raised for an impossible date such as 2026-13-01, which
        # the `preamble-date` rule reports.
        return
    if not isinstance(parsed, dict):
        return
    for name, header in by_name.items():
        value = parsed.get(name)
        if isinstance(value, (list, dict)):
            report.error(header.line, "preamble-yaml", "preamble values must be plain text, not YAML lists or maps")
            continue
        text = "" if value is None else str(value)
        if text != header.value:
            report.error(header.line, "preamble-yaml", f"YAML reads preamble header `{name}` as `{text}`; rephrase or quote the value")


def check_proposal_words(report: Report, header: Header, number: int | None) -> None:
    if STANDARD_RE.search(header.value):
        report.error(header.line, "preamble-re-standard", f"`{header.name}` must not contain the word `standard` or a variation of it")
    if UNDASHED_MENTION_RE.search(header.value):
        report.error(header.line, "preamble-re-dash", f"`{header.name}` must reference proposals as `MIP-N` or `MRC-N`, not `MIP N` or `MIPN`")
    if number is not None and re.search(rf"\b(?:mip|mrc)[\s-]*{number}\b", header.value, re.IGNORECASE):
        report.error(header.line, "preamble-re-own-number", f"`{header.name}` must not contain this MIP's number")


def check_title(report: Report, header: Header | None, number: int | None) -> None:
    if not header:
        return
    if not 2 <= len(header.value) <= MAX_TITLE_LENGTH:
        report.error(
            header.line,
            "preamble-len-title",
            f"`title` must be between 2 and {MAX_TITLE_LENGTH} characters long, it has {len(header.value)}",
        )
    check_proposal_words(report, header, number)
    violations = title_case_violations(header.value)
    if violations:
        report.warning(header.line, "preamble-title-case", f"`title` should be in title case; capitalize {one_of(violations)}")


def check_description(report: Report, header: Header | None, number: int | None) -> None:
    if not header:
        return
    if not 2 <= len(header.value) <= MAX_DESCRIPTION_LENGTH:
        report.error(
            header.line,
            "preamble-len-description",
            f"`description` must be between 2 and {MAX_DESCRIPTION_LENGTH} characters long, it has {len(header.value)}",
        )
    check_proposal_words(report, header, number)
    if header.value and header.value[0].isalpha() and not header.value[0].isupper():
        report.warning(header.line, "preamble-description-case", "`description` should be in sentence case")


def check_list(report: Report, header: Header) -> list[str]:
    items = [item.strip() for item in header.value.split(",")]
    if not header.value or any(not item for item in items) or ", ".join(items) != header.value:
        report.error(header.line, "preamble-list", f"`{header.name}` items must be separated by a comma and a single space")
    return [item for item in items if item]


def check_author(report: Report, header: Header | None) -> None:
    if not header:
        return
    has_user = False
    for entry in check_list(report, header):
        match = AUTHOR_RE.match(entry)
        if not match:
            report.error(
                header.line,
                "preamble-author",
                f"author `{entry}` must be written as `Name`, `Name (@github)`, `Name <email>` or `Name (@github) <email>`",
            )
            continue
        has_user |= bool(match.group("user") or match.group("only_user"))
    if not has_user:
        report.error(header.line, "preamble-author-github", "at least one author must include a GitHub username in the form `(@username)`")


def check_discussions_to(report: Report, header: Header | None) -> None:
    if not header:
        return
    url = split_url(header.value)
    if url.scheme != "https" or url.netloc.lower() != FORUM_HOST:
        report.error(header.line, "preamble-discussions-to", f"`discussions-to` must be a thread on https://{FORUM_HOST}/")


def check_type_and_category(report: Report, type_: Header | None, category: Header | None) -> str | None:
    if not type_:
        return None
    if type_.value not in CATEGORIES:
        report.error(type_.line, "preamble-enum", f"`type` must be one of {one_of(list(CATEGORIES))}")
        return None
    allowed = CATEGORIES[type_.value]
    if allowed and not category:
        report.error(type_.line, "preamble-req-category", f"`{type_.value}` MIPs must have a `category` header")
    if not category:
        return None
    if not allowed:
        report.error(category.line, "preamble-category", f"`{type_.value}` MIPs must not have a `category` header")
    elif category.value not in allowed:
        report.error(category.line, "preamble-enum", f"`category` of a `{type_.value}` MIP must be one of {one_of(allowed)}")
    else:
        return category.value
    return None


def check_date(report: Report, header: Header | None) -> None:
    if not header:
        return
    try:
        valid = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", header.value)) and bool(date.fromisoformat(header.value))
    except ValueError:
        valid = False
    if not valid:
        report.error(header.line, "preamble-date", f"`{header.name}` must be a date in the form yyyy-mm-dd")


def check_requires(report: Report, header: Header | None, repo: Repo) -> None:
    if not header:
        return
    for item in check_list(report, header):
        if not re.fullmatch(r"[1-9][0-9]*", item):
            report.error(header.line, "preamble-uint-list", "`requires` must be a comma-separated list of MIP numbers")
        elif repo.proposal_kind(int(item)) is None:
            report.error(header.line, "preamble-requires-exists", f"`requires` references MIP-{item}, which does not exist in this repository")


def check_file_name(report: Report, path: Path, repo: Repo, preamble: Preamble, is_draft_file: bool) -> None:
    kind = "MRC" if preamble.category == "MRC" else "MIP"
    directory = f"{kind}s"
    if preamble.number is None:
        if not is_draft_file:
            return
        expected = f"{kind}-draft_<abbreviated title>.md"
        ok = path.name.startswith(f"{kind}-draft_")
    else:
        expected = f"{kind}-{preamble.number}.md"
        ok = path.name == expected
    if not ok or path.parent.name != directory:
        report.error(1, "file-name", f"this {kind} must be saved as `{directory}/{expected}`")
    if preamble.number is not None:
        other = "MIP" if kind == "MRC" else "MRC"
        twin = repo.root / f"{other}s" / f"{other}-{preamble.number}.md"
        if twin.is_file():
            report.error(1, "file-name-dup", f"number {preamble.number} is already used by `{other}s/{twin.name}`")
