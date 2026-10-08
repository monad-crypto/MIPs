#!/usr/bin/env python3
"""
Lint MIP and MRC documents against MIP-1 and mip-template.md.

Usage:
    python3 scripts/lint_mips.py [--root DIR] [FILE ...]

Without FILE arguments every document under MIPs/ and MRCs/ is linted.
Each finding is printed as `path:line:col: level: message [rule]`.
Under GitHub Actions findings are emitted as workflow commands instead,
which renders them as annotations on the pull request diff.

The exit status is 1 when at least one error was found. Warnings cover
rules that cannot be checked reliably and never fail the run.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install -r scripts/requirements.txt")

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

SECTION_ORDER = [
    "Abstract",
    "Motivation",
    "Specification",
    "Rationale",
    "Backwards Compatibility",
    "Test Cases",
    "Reference Implementation",
    "Security Considerations",
    "Copyright",
]
REQUIRED_SECTIONS = ["Abstract", "Specification", "Rationale", "Security Considerations", "Copyright"]
RECOMMENDED_SECTIONS = {"Core": ["Test Cases"]}
COPYRIGHT_TEXT = "Copyright and related rights waived via [CC0](../LICENSE.md)."
DRAFT_PLACEHOLDERS = {"Rationale": "TBD", "Security Considerations": "Needs discussion."}

# MIP-1 describes the process itself and does not follow the template.
BODY_UNCHECKED = {1}

SMALL_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "so", "yet", "as", "at",
    "by", "from", "in", "into", "of", "off", "on", "onto", "out", "over", "per",
    "to", "up", "via", "with", "vs",
}

ALLOWED_EXTERNAL_LINKS = [
    re.compile(pattern)
    for pattern in [
        r"^https://(?:dx\.)?doi\.org/10\.\d{4,9}/\S+$",
        r"^https://arxiv\.org/(?:abs|pdf)/\d{4}\.\d{4,5}v\d+$",
        r"^https://(?:www\.)?github\.com/ethereum/yellowpaper/(?:blob|tree)/[0-9a-f]{40}/.+$",
        r"^https://(?:www\.)?github\.com/ethereum/yellowpaper/commit/[0-9a-f]{40}$",
        r"^https://(?:www\.)?github\.com/ethereum/execution-specs/(?:blob|tree)/[0-9a-f]{40}/.+$",
        r"^https://(?:www\.)?github\.com/ethereum/execution-specs/commit/[0-9a-f]{40}$",
        r"^https://(?:www\.)?github\.com/ethereum/EIPs/(?:blob|tree)/[0-9a-f]{40}/.+$",
        r"^https://(?:www\.)?github\.com/ethereum/EIPs/commit/[0-9a-f]{40}$",
        r"^https://eips\.ethereum\.org/EIPS/eip-\d+(?:#.*)?$",
        r"^https://(?:www\.)?github\.com/bitcoin/bips/(?:blob|tree)/[0-9a-f]{40}/.+$",
        r"^https://(?:www\.)?github\.com/bitcoin/bips/commit/[0-9a-f]{40}$",
        r"^https://(?:www\.)?github\.com/ChainAgnostic/CAIPs/(?:blob|tree)/[0-9a-f]{40}/.+$",
        r"^https://(?:www\.)?github\.com/ChainAgnostic/CAIPs/commit/[0-9a-f]{40}$",
        r"^https://(?:www\.)?(?:rfc-editor\.org|ietf\.org)/rfc/rfc\d+(?:\.(?:txt|html))?(?:#.*)?$",
        r"^https://datatracker\.ietf\.org/doc/html/rfc\d+(?:#.*)?$",
        r"^https://www\.w3\.org/TR/\d{4}/.+$",
    ]
]

HEADER_LINE_RE = re.compile(r"^([a-z][a-z0-9-]*):(.*)$")
DRAFT_FILE_RE = re.compile(r"^(MIP|MRC)-draft_[A-Za-z0-9_-]+\.md$")
AUTHOR_RE = re.compile(
    r"^(?:(?P<name>[^()<>@,]+?)"
    r"(?: \((?P<user>@[A-Za-z0-9-]+)\))?"
    r"(?: <(?P<email>[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>)?"
    r"|\((?P<only_user>@[A-Za-z0-9-]+)\))$"
)
MENTION_RE = re.compile(r"\b(mip|mrc)-(\d+)\b", re.IGNORECASE)
UNDASHED_MENTION_RE = re.compile(r"\b(?:mip|mrc)\s*\d+\b", re.IGNORECASE)
STANDARD_RE = re.compile(r"standar", re.IGNORECASE)
RFC2119_RE = re.compile(
    r"\b(?:MUST(?: NOT)?|REQUIRED|SHALL(?: NOT)?|SHOULD(?: NOT)?|(?:NOT )?RECOMMENDED|MAY|OPTIONAL)\b"
)

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
HEADING_NO_SPACE_RE = re.compile(r"^ {0,3}#{1,6}[^#\s]")
LINK_LABEL = r"((?:[^\[\]]|\[[^\[\]]*\])*)"
LINK_TITLE = r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?"
INLINE_LINK_RE = re.compile(r"(!?)\[" + LINK_LABEL + r"\]\(\s*<?([^\s<>()]*)>?" + LINK_TITLE + r"\s*\)")
REF_LINK_RE = re.compile(r"(!?)\[" + LINK_LABEL + r"\]\[([^\]]*)\]")
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*<?(\S+?)>?" + LINK_TITLE + r"\s*$")
AUTOLINK_RE = re.compile(r"<(https?://[^\s>]+)>")


@dataclass
class Finding:
    path: str
    line: int
    col: int
    level: str
    rule: str
    message: str

    def text(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.level}: {self.message} [{self.rule}]"

    def github(self) -> str:
        def escape(value: str, properties: bool = False) -> str:
            value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            if properties:
                value = value.replace(":", "%3A").replace(",", "%2C")
            return value

        location = f"file={escape(self.path, True)},line={self.line},col={self.col},title={escape(self.rule, True)}"
        return f"::{self.level} {location}::{escape(self.message)}"


@dataclass
class Header:
    line: int
    name: str
    raw: str

    @property
    def value(self) -> str:
        return self.raw.strip()


@dataclass
class Heading:
    line: int
    level: int
    text: str


@dataclass
class Link:
    line: int
    col: int
    dest: str
    text_start: int = -1
    text_end: int = -1


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


def blank(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def blank_code_spans(text: str) -> str:
    runs = [(m.start(), m.end()) for m in re.finditer(r"`+", text)]
    i = 0
    while i < len(runs):
        start, end = runs[i]
        length = end - start
        closing = next((j for j in range(i + 1, len(runs)) if runs[j][1] - runs[j][0] == length), None)
        if closing is None:
            i += 1
            continue
        text = blank(text, start, runs[closing][1])
        i = closing + 1
    return text


class Body:
    """
    Markdown body with fenced code, inline code, HTML comments and link
    targets blanked out, so that rules can scan prose by column.
    """

    def __init__(self, lines: list[str], first_line: int):
        self.headings: list[Heading] = []
        self.links: list[Link] = []
        self.comments: list[tuple[int, int]] = []
        self.headings_without_space: list[int] = []
        self.prose: list[tuple[int, str]] = []
        self._scan(lines, first_line)

    def _scan(self, lines: list[str], first_line: int) -> None:
        refs = self._reference_definitions(lines)
        fence: tuple[str, int] | None = None
        in_comment = False
        for offset, raw in enumerate(lines):
            lineno = first_line + offset
            if fence:
                if re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{fence[1]},}}[ \t]*$", raw):
                    fence = None
                continue
            opening = FENCE_RE.match(raw)
            if opening and not in_comment:
                fence = (opening.group(1)[0], len(opening.group(1)))
                continue
            text, in_comment = self._blank_comments(raw, lineno, in_comment)
            text = blank_code_spans(text)
            if HEADING_NO_SPACE_RE.match(text):
                self.headings_without_space.append(lineno)
            heading = HEADING_RE.match(text)
            if heading:
                self.headings.append(Heading(lineno, len(heading.group(1)), (heading.group(2) or "").strip()))
            text = self._extract_links(text, lineno, refs)
            self.prose.append((lineno, text))

    @staticmethod
    def _reference_definitions(lines: list[str]) -> dict[str, str]:
        refs = {}
        for raw in lines:
            definition = REF_DEF_RE.match(raw)
            if definition:
                refs[definition.group(1).lower()] = definition.group(2)
        return refs

    def _blank_comments(self, text: str, lineno: int, in_comment: bool) -> tuple[str, bool]:
        pos = 0
        while True:
            if in_comment:
                end = text.find("-->", pos)
                if end < 0:
                    return blank(text, pos, len(text)), True
                text = blank(text, pos, end + 3)
                pos = end + 3
                in_comment = False
            start = text.find("<!--", pos)
            if start < 0:
                return text, False
            self.comments.append((lineno, start + 1))
            in_comment = True
            pos = start

    def _extract_links(self, text: str, lineno: int, refs: dict[str, str]) -> str:
        definition = REF_DEF_RE.match(text)
        if definition:
            self.links.append(Link(lineno, 1, definition.group(2)))
            return blank(text, 0, len(text))

        def inline(m: re.Match) -> str:
            image, dest = m.group(1), m.group(3)
            if image:
                self.links.append(Link(lineno, m.start() + 1, dest))
                return blank(m.group(0), 0, len(m.group(0)))
            self.links.append(Link(lineno, m.start() + 1, dest, m.start(2), m.end(2)))
            return blank(m.group(0), m.end(2) - m.start() + 1, len(m.group(0)))

        def reference(m: re.Match) -> str:
            image, label = m.group(1), m.group(3) or m.group(2)
            dest = refs.get(label.lower())
            if dest is None:
                return m.group(0)
            if image:
                self.links.append(Link(lineno, m.start() + 1, dest))
                return blank(m.group(0), 0, len(m.group(0)))
            self.links.append(Link(lineno, m.start() + 1, dest, m.start(2), m.end(2)))
            return blank(m.group(0), m.end(2) - m.start() + 1, len(m.group(0)))

        def autolink(m: re.Match) -> str:
            self.links.append(Link(lineno, m.start() + 1, m.group(1)))
            return blank(m.group(0), 0, len(m.group(0)))

        text = INLINE_LINK_RE.sub(inline, text)
        text = REF_LINK_RE.sub(reference, text)
        return AUTOLINK_RE.sub(autolink, text)


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


class DocumentLinter:
    def __init__(self, path: Path, repo: Repo):
        self.path = path
        self.repo = repo
        self.findings: list[Finding] = []
        self.number: int | None = None
        self.status: str | None = None
        self.category: str | None = None
        try:
            self.display = str(path.resolve().relative_to(Path.cwd()))
        except ValueError:
            self.display = str(path)

    def report(self, level: str, line: int, col: int, rule: str, message: str) -> None:
        self.findings.append(Finding(self.display, line, col, level, rule, message))

    def error(self, line: int, rule: str, message: str, col: int = 1) -> None:
        self.report("error", line, col, rule, message)

    def warning(self, line: int, rule: str, message: str, col: int = 1) -> None:
        self.report("warning", line, col, rule, message)

    def lint(self) -> list[Finding]:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---":
            self.error(1, "preamble-missing", "the document must start with a `---` preamble")
            return self.findings
        try:
            end = lines.index("---", 1)
        except ValueError:
            self.error(1, "preamble-missing", "the preamble is not closed with `---`")
            return self.findings
        headers = self.parse_headers(lines[1:end])
        self.check_preamble(headers, lines[1:end])
        if self.number not in BODY_UNCHECKED:
            self.check_body(lines[end + 1 :], end + 2)
        return self.findings

    def parse_headers(self, lines: list[str]) -> list[Header]:
        headers = []
        for lineno, line in enumerate(lines, start=2):
            match = HEADER_LINE_RE.match(line)
            if not match:
                self.error(lineno, "preamble-header", "preamble lines must be `name: value` headers")
                continue
            headers.append(Header(lineno, match.group(1), match.group(2)))
        return headers

    def check_preamble(self, headers: list[Header], lines: list[str]) -> None:
        by_name: dict[str, Header] = {}
        last_index = -1
        for header in headers:
            if header.name in by_name:
                self.error(header.line, "preamble-no-dup", f"preamble header `{header.name}` appears more than once")
                continue
            by_name[header.name] = header
            if header.name not in HEADER_ORDER:
                self.error(header.line, "preamble-unknown", f"`{header.name}` is not a MIP preamble header")
                continue
            index = HEADER_ORDER.index(header.name)
            if index < last_index:
                self.error(
                    header.line,
                    "preamble-order",
                    f"preamble header `{header.name}` is out of order; the order is {', '.join(HEADER_ORDER)}",
                )
            last_index = max(last_index, index)
            if header.raw != (f" {header.value}" if header.value else ""):
                self.error(
                    header.line,
                    "preamble-trim",
                    f"preamble header `{header.name}` must be followed by one space and have no trailing whitespace",
                )
        self.check_yaml(lines, by_name)

        is_draft_file = DRAFT_FILE_RE.match(self.path.name) is not None
        for name in REQUIRED_HEADERS:
            if name not in by_name and not (name == "mip" and is_draft_file):
                self.error(1, "preamble-req", f"preamble header `{name}` is required")

        mip = by_name.get("mip")
        if mip:
            if re.fullmatch(r"[1-9][0-9]*", mip.value):
                self.number = int(mip.value)
            else:
                self.error(mip.line, "preamble-uint", "preamble header `mip` must be a positive integer")

        self.check_title(by_name.get("title"))
        self.check_description(by_name.get("description"))
        self.check_author(by_name.get("author"))
        self.check_discussions_to(by_name.get("discussions-to"))

        status = by_name.get("status")
        if status:
            if status.value in STATUSES:
                self.status = status.value
            else:
                self.error(status.line, "preamble-enum", f"`status` must be one of {one_of(STATUSES)}")

        self.check_type_and_category(by_name.get("type"), by_name.get("category"))
        self.check_date(by_name.get("created"))
        self.check_date(by_name.get("last-call-deadline"))
        if self.status == "Last Call" and "last-call-deadline" not in by_name:
            self.error(status.line, "preamble-req-last-call-deadline", "`Last Call` MIPs must have a `last-call-deadline` header")
        if self.status == "Withdrawn" and "withdrawal-reason" not in by_name:
            self.error(status.line, "preamble-req-withdrawal-reason", "`Withdrawn` MIPs must have a `withdrawal-reason` header")
        self.check_requires(by_name.get("requires"))
        if self.category == "Hardfork" and "requires" not in by_name:
            self.error(by_name["category"].line, "preamble-req-requires", "`Hardfork` MIPs must list the included MIPs in `requires`")
        self.check_file_name(is_draft_file)

    def check_yaml(self, lines: list[str], by_name: dict[str, Header]) -> None:
        try:
            parsed = yaml.safe_load("\n".join(lines))
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            line = mark.line + 2 if mark else 2
            problem = " ".join(str(exc).split())
            self.error(line, "preamble-yaml", f"the preamble is not valid YAML, so Jekyll cannot render the page: {problem}")
            return
        except ValueError:
            # Raised for an impossible date such as 2026-13-01, which
            # the `preamble-date` rule reports.
            return
        if not isinstance(parsed, dict):
            return
        for name, header in by_name.items():
            value = parsed.get(name)
            text = "" if value is None else str(value)
            if text != header.value:
                self.error(header.line, "preamble-yaml", f"YAML reads preamble header `{name}` as `{text}`; rephrase or quote the value")

    def check_proposal_words(self, header: Header) -> None:
        if STANDARD_RE.search(header.value):
            self.error(header.line, "preamble-re-standard", f"`{header.name}` must not contain the word `standard` or a variation of it")
        if UNDASHED_MENTION_RE.search(header.value):
            self.error(header.line, "preamble-re-dash", f"`{header.name}` must reference proposals as `MIP-N` or `MRC-N`, not `MIP N` or `MIPN`")
        if self.number is not None and re.search(rf"\b(?:mip|mrc)[\s-]*{self.number}\b", header.value, re.IGNORECASE):
            self.error(header.line, "preamble-re-own-number", f"`{header.name}` must not contain this MIP's number")

    def check_title(self, header: Header | None) -> None:
        if not header:
            return
        if not 2 <= len(header.value) <= MAX_TITLE_LENGTH:
            self.error(
                header.line,
                "preamble-len-title",
                f"`title` must be between 2 and {MAX_TITLE_LENGTH} characters long, it has {len(header.value)}",
            )
        self.check_proposal_words(header)
        violations = title_case_violations(header.value)
        if violations:
            self.warning(header.line, "preamble-title-case", f"`title` should be in title case; capitalize {one_of(violations)}")

    def check_description(self, header: Header | None) -> None:
        if not header:
            return
        if not 2 <= len(header.value) <= MAX_DESCRIPTION_LENGTH:
            self.error(
                header.line,
                "preamble-len-description",
                f"`description` must be between 2 and {MAX_DESCRIPTION_LENGTH} characters long, it has {len(header.value)}",
            )
        self.check_proposal_words(header)
        if header.value and header.value[0].isalpha() and not header.value[0].isupper():
            self.warning(header.line, "preamble-description-case", "`description` should be in sentence case")

    def check_list(self, header: Header) -> list[str]:
        items = [item.strip() for item in header.value.split(",")]
        if not header.value or any(not item for item in items) or ", ".join(items) != header.value:
            self.error(header.line, "preamble-list", f"`{header.name}` items must be separated by a comma and a single space")
        return [item for item in items if item]

    def check_author(self, header: Header | None) -> None:
        if not header:
            return
        has_user = False
        for entry in self.check_list(header):
            match = AUTHOR_RE.match(entry)
            if not match:
                self.error(
                    header.line,
                    "preamble-author",
                    f"author `{entry}` must be written as `Name`, `Name (@github)`, `Name <email>` or `Name (@github) <email>`",
                )
                continue
            has_user |= bool(match.group("user") or match.group("only_user"))
        if not has_user:
            self.error(header.line, "preamble-author-github", "at least one author must include a GitHub username in the form `(@username)`")

    def check_discussions_to(self, header: Header | None) -> None:
        if not header:
            return
        url = urlsplit(header.value)
        if url.scheme not in ("http", "https") or not url.netloc:
            self.error(header.line, "preamble-url", "`discussions-to` must be a URL")
            return
        host = url.netloc.lower().removeprefix("www.")
        if (host == "github.com" and re.search(r"/(?:pull|issues)/\d+", url.path)) or host.endswith("reddit.com"):
            self.error(header.line, "preamble-discussions-to", "`discussions-to` must not point to a GitHub pull request or issue, or to Reddit")
        elif host != FORUM_HOST:
            self.warning(header.line, "preamble-discussions-to", f"`discussions-to` should point to a thread on https://{FORUM_HOST}/")

    def check_type_and_category(self, type_: Header | None, category: Header | None) -> None:
        if not type_:
            return
        if type_.value not in CATEGORIES:
            self.error(type_.line, "preamble-enum", f"`type` must be one of {one_of(list(CATEGORIES))}")
            return
        allowed = CATEGORIES[type_.value]
        if allowed and not category:
            self.error(type_.line, "preamble-req-category", f"`{type_.value}` MIPs must have a `category` header")
        if not category:
            return
        if not allowed:
            self.error(category.line, "preamble-category", f"`{type_.value}` MIPs must not have a `category` header")
        elif category.value not in allowed:
            self.error(category.line, "preamble-enum", f"`category` of a `{type_.value}` MIP must be one of {one_of(allowed)}")
        else:
            self.category = category.value

    def check_date(self, header: Header | None) -> None:
        if not header:
            return
        try:
            valid = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", header.value)) and bool(date.fromisoformat(header.value))
        except ValueError:
            valid = False
        if not valid:
            self.error(header.line, "preamble-date", f"`{header.name}` must be a date in the form yyyy-mm-dd")

    def check_requires(self, header: Header | None) -> None:
        if not header:
            return
        for item in self.check_list(header):
            if not re.fullmatch(r"[1-9][0-9]*", item):
                self.error(header.line, "preamble-uint-list", "`requires` must be a comma-separated list of MIP numbers")
            elif self.repo.proposal_kind(int(item)) is None:
                self.error(header.line, "preamble-requires-exists", f"`requires` references MIP-{item}, which does not exist in this repository")

    def check_file_name(self, is_draft_file: bool) -> None:
        kind = "MRC" if self.category == "MRC" else "MIP"
        directory = f"{kind}s"
        if self.number is None:
            if not is_draft_file:
                return
            expected = f"{kind}-draft_<abbreviated title>.md"
            ok = self.path.name.startswith(f"{kind}-draft_")
        else:
            expected = f"{kind}-{self.number}.md"
            ok = self.path.name == expected
        if not ok or self.path.parent.name != directory:
            self.error(1, "file-name", f"this {kind} must be saved as `{directory}/{expected}`")

    def check_body(self, lines: list[str], first_line: int) -> None:
        body = Body(lines, first_line)
        for line, col in body.comments:
            self.error(line, "markdown-html-comments", "HTML comments must be removed before submitting", col)
        for line in body.headings_without_space:
            self.error(line, "markdown-headings-space", "headings must have a space after the `#` characters")
        self.check_sections(body, lines, first_line)
        self.check_links(body)
        self.check_mentions(body)
        self.check_rfc2119(body)

    def check_sections(self, body: Body, lines: list[str], first_line: int) -> None:
        sections = [heading for heading in body.headings if heading.level == 2]
        canonical = {name.lower(): name for name in SECTION_ORDER}
        for heading in sections:
            expected = canonical.get(heading.text.lower())
            if expected and heading.text != expected:
                self.error(heading.line, "markdown-section-name", f"section headings must match the template: `## {expected}`")
        names = {heading.text.lower() for heading in sections}
        for name in REQUIRED_SECTIONS:
            if name.lower() not in names:
                self.error(1, "markdown-req-section", f"the `## {name}` section is required")
        for name in RECOMMENDED_SECTIONS.get(self.category, []):
            if name.lower() not in names:
                self.warning(1, "markdown-req-section", f"`{self.category}` MIPs should have a `## {name}` section")

        last_index = -1
        seen = set()
        for heading in sections:
            if heading.text not in SECTION_ORDER:
                continue
            if heading.text in seen:
                self.error(heading.line, "markdown-section-dup", f"`## {heading.text}` appears more than once")
                continue
            seen.add(heading.text)
            index = SECTION_ORDER.index(heading.text)
            if index < last_index:
                self.error(
                    heading.line,
                    "markdown-order-section",
                    f"`## {heading.text}` is out of order; the order is {', '.join(SECTION_ORDER)}",
                )
            last_index = max(last_index, index)

        for i, heading in enumerate(sections):
            end = sections[i + 1].line if i + 1 < len(sections) else first_line + len(lines)
            content = [
                line.strip()
                for line in lines[heading.line - first_line + 1 : end - first_line]
                if line.strip() and not REF_DEF_RE.match(line)
            ]
            if heading.text == "Copyright" and content != [COPYRIGHT_TEXT]:
                hint = "; the section contains a non-breaking space" if any("\u00a0" in line for line in content) else ""
                self.error(heading.line, "markdown-copyright", f"the Copyright section must contain exactly `{COPYRIGHT_TEXT}`{hint}")
            placeholder = DRAFT_PLACEHOLDERS.get(heading.text)
            if placeholder and content == [placeholder] and self.status == "Final":
                self.error(heading.line, "markdown-placeholder", f"a Final MIP must not leave the `{placeholder}` placeholder in place")

    def resolve(self, dest: str) -> Path | None:
        url = urlsplit(dest)
        if url.scheme or not url.path:
            return None
        return (self.path.parent / unquote(url.path)).resolve()

    def check_links(self, body: Body) -> None:
        for link in body.links:
            url = urlsplit(link.dest)
            if url.scheme:
                if url.scheme in ("http", "https") and any(pattern.match(link.dest) for pattern in ALLOWED_EXTERNAL_LINKS):
                    continue
                host = url.netloc.lower().removeprefix("www.")
                if host == "mips.monad.xyz" or (host == "github.com" and url.path.lower().startswith("/monad-crypto/mips")):
                    self.error(link.line, "markdown-rel-links", f"links within this repository must be relative: `{link.dest}`", link.col)
                else:
                    self.error(
                        link.line,
                        "markdown-rel-links",
                        f"external link `{link.dest}` is not permitted; see the permitted external resources in MIP-1",
                        link.col,
                    )
                continue
            target = self.resolve(link.dest)
            if target is not None and not target.exists():
                self.error(link.line, "markdown-rel-links", f"the relative link target `{url.path}` does not exist", link.col)

    def check_mentions(self, body: Body) -> None:
        links_by_line: dict[int, list[Link]] = {}
        for link in body.links:
            if link.text_start >= 0:
                links_by_line.setdefault(link.line, []).append(link)
        seen: set[int] = set()
        for lineno, text in body.prose:
            for match in UNDASHED_MENTION_RE.finditer(text):
                self.error(
                    lineno,
                    "markdown-re-dash",
                    "proposals must be referenced as `MIP-N` or `MRC-N`, not `MIP N` or `MIPN`",
                    match.start() + 1,
                )
            for match in MENTION_RE.finditer(text):
                prefix, number = match.group(1), int(match.group(2))
                col = match.start() + 1
                written = f"{prefix.upper()}-{number}"
                if prefix != prefix.upper():
                    self.error(lineno, "markdown-re-dash", f"proposals must be referenced in upper case: `{written}`", col)
                target = self.repo.proposal_path(number)
                if target is None:
                    self.error(lineno, "markdown-refs", f"{written} does not exist in this repository", col)
                    continue
                kind = target.name[:3]
                canonical = f"{kind}-{number}"
                if kind != prefix.upper():
                    article = "an" if kind == "MRC" else "a"
                    self.error(lineno, "markdown-mip-mrc", f"{canonical} is {article} {kind} and must be referenced as `{canonical}`", col)
                if number == self.number or number in seen:
                    continue
                seen.add(number)
                linked = any(
                    link.text_start <= match.start() and match.end() <= link.text_end and self.resolve(link.dest) == target
                    for link in links_by_line.get(lineno, [])
                )
                if not linked:
                    relative = os.path.relpath(target, self.path.parent)
                    if not relative.startswith("."):
                        relative = f"./{relative}"
                    self.error(
                        lineno,
                        "markdown-link-first",
                        f"the first reference to {canonical} must be a relative link: `[{canonical}]({relative})`",
                        col,
                    )

    def check_rfc2119(self, body: Body) -> None:
        sections = [heading for heading in body.headings if heading.level == 2]
        section = None
        index = 0
        for lineno, text in body.prose:
            while index < len(sections) and sections[index].line <= lineno:
                section = sections[index].text
                index += 1
            if section == "Specification":
                continue
            for match in RFC2119_RE.finditer(text):
                self.error(
                    lineno,
                    "markdown-rfc2119",
                    f"the RFC 2119 keyword `{match.group(0)}` must only be used in the Specification section",
                    match.start() + 1,
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path, help="documents to lint (default: all MIPs and MRCs)")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root used to resolve referenced proposals (default: the parent of this script's directory)",
    )
    args = parser.parse_args(argv)
    repo = Repo(args.root)
    files = args.files or repo.all_proposals()
    github = os.environ.get("GITHUB_ACTIONS") == "true"

    counts = {"error": 0, "warning": 0}
    for path in files:
        for finding in DocumentLinter(path, repo).lint():
            counts[finding.level] += 1
            print(finding.github() if github else finding.text())
    print(f"{len(files)} file(s) checked: {counts['error']} error(s), {counts['warning']} warning(s)")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
