import os
import re
from pathlib import Path
from urllib.parse import unquote

from .findings import Report
from .markdown import REF_DEF_RE, Body, Link, split_url
from .preamble import Preamble
from .repo import MENTION_RE, UNDASHED_MENTION_RE, Repo

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

RFC2119_RE = re.compile(
    r"\b(?:MUST(?: NOT)?|REQUIRED|SHALL(?: NOT)?|SHOULD(?: NOT)?|(?:NOT )?RECOMMENDED|MAY|OPTIONAL)\b"
)


def check_markup(report: Report, body: Body) -> None:
    if body.unclosed_fence is not None:
        report.error(body.unclosed_fence, "markdown-unclosed-fence", "this code fence is never closed, so the rest of the document renders as text")
    for line, col in body.unparsed_links:
        report.error(line, "markdown-link-syntax", "this link could not be parsed; avoid nested brackets in the link text and whitespace in the URL", col)
    for line, col, tag in body.html_tags:
        report.error(
            line,
            "markdown-no-html",
            f"raw HTML `{tag}` is not allowed; only bare `<sup>` and `<sub>` are permitted, and a less-than sign in prose needs a space after it",
            col,
        )
    for line, col in body.kramdown:
        report.error(line, "markdown-no-kramdown", "kramdown attribute lists and extensions (`{:`) are not allowed", col)
    for line, col in body.comments:
        report.error(line, "markdown-html-comments", "HTML comments must be removed before submitting", col)
    for line in body.headings_without_space:
        report.error(line, "markdown-headings-space", "headings must have a space after the `#` characters")


def check_sections(report: Report, body: Body, preamble: Preamble) -> None:
    sections = [heading for heading in body.headings if heading.level == 2]
    canonical = {name.lower(): name for name in SECTION_ORDER}
    for heading in sections:
        expected = canonical.get(heading.text.lower())
        if expected and heading.text != expected:
            report.error(heading.line, "markdown-section-name", f"section headings must match the template: `## {expected}`")
    names = {heading.text.lower() for heading in sections}
    for name in REQUIRED_SECTIONS:
        if name.lower() not in names:
            report.error(1, "markdown-req-section", f"the `## {name}` section is required")
    for name in RECOMMENDED_SECTIONS.get(preamble.category, []):
        if name.lower() not in names:
            report.warning(1, "markdown-req-section", f"`{preamble.category}` MIPs should have a `## {name}` section")

    last_index = -1
    seen = set()
    for heading in sections:
        if heading.text not in SECTION_ORDER:
            continue
        if heading.text in seen:
            report.error(heading.line, "markdown-section-dup", f"`## {heading.text}` appears more than once")
            continue
        seen.add(heading.text)
        index = SECTION_ORDER.index(heading.text)
        if index < last_index:
            report.error(
                heading.line,
                "markdown-order-section",
                f"`## {heading.text}` is out of order; the order is {', '.join(SECTION_ORDER)}",
            )
        last_index = max(last_index, index)

    for i, heading in enumerate(sections):
        end = sections[i + 1].line if i + 1 < len(sections) else body.first_line + len(body.lines)
        content = [
            line.strip()
            for line in body.lines[heading.line - body.first_line + 1 : end - body.first_line]
            if line.strip() and not REF_DEF_RE.match(line)
        ]
        if heading.text == "Copyright" and content != [COPYRIGHT_TEXT]:
            hint = "; the section contains a non-breaking space" if any(" " in line for line in content) else ""
            report.error(heading.line, "markdown-copyright", f"the Copyright section must contain exactly `{COPYRIGHT_TEXT}`{hint}")
        placeholder = DRAFT_PLACEHOLDERS.get(heading.text)
        if placeholder and content == [placeholder] and preamble.status == "Final":
            report.error(heading.line, "markdown-placeholder", f"a Final MIP must not leave the `{placeholder}` placeholder in place")


def resolve(path: Path, dest: str) -> Path | None:
    url = split_url(dest)
    if url.scheme or url.netloc or not url.path:
        return None
    return (path.parent / unquote(url.path)).resolve()


def check_links(report: Report, body: Body, path: Path, repo: Repo) -> None:
    for link in body.links:
        url = split_url(link.dest)
        if url.scheme or url.netloc:
            if url.scheme in ("http", "https") and any(pattern.match(link.dest) for pattern in ALLOWED_EXTERNAL_LINKS):
                continue
            host = url.netloc.lower().removeprefix("www.")
            if host == "mips.monad.xyz" or (host == "github.com" and url.path.lower().startswith("/monad-crypto/mips")):
                report.error(link.line, "markdown-rel-links", f"links within this repository must be relative: `{link.dest}`", link.col)
            else:
                report.error(
                    link.line,
                    "markdown-rel-links",
                    f"external link `{link.dest}` is not permitted; see the permitted external resources in MIP-1",
                    link.col,
                )
            continue
        target = resolve(path, link.dest)
        if target is None:
            continue
        if not target.is_relative_to(repo.root):
            report.error(link.line, "markdown-rel-links", f"the relative link `{url.path}` points outside the repository", link.col)
        elif not target.exists():
            report.error(link.line, "markdown-rel-links", f"the relative link target `{url.path}` does not exist", link.col)


def check_mentions(report: Report, body: Body, path: Path, repo: Repo, number: int | None) -> None:
    links_by_line: dict[int, list[Link]] = {}
    for link in body.links:
        if link.text_start >= 0:
            links_by_line.setdefault(link.line, []).append(link)
    seen: set[int] = set()
    for lineno, text in body.prose:
        for match in UNDASHED_MENTION_RE.finditer(text):
            report.error(
                lineno,
                "markdown-re-dash",
                "proposals must be referenced as `MIP-N` or `MRC-N`, not `MIP N` or `MIPN`",
                match.start() + 1,
            )
        for match in MENTION_RE.finditer(text):
            prefix, referenced = match.group(1), int(match.group(2))
            col = match.start() + 1
            written = f"{prefix.upper()}-{referenced}"
            if prefix != prefix.upper():
                report.error(lineno, "markdown-re-dash", f"proposals must be referenced in upper case: `{written}`", col)
            target = repo.proposal_path(referenced)
            if target is None:
                report.error(lineno, "markdown-refs", f"{written} does not exist in this repository", col)
                continue
            kind = target.name[:3]
            canonical = f"{kind}-{referenced}"
            if kind != prefix.upper():
                article = "an" if kind == "MRC" else "a"
                report.error(lineno, "markdown-mip-mrc", f"{canonical} is {article} {kind} and must be referenced as `{canonical}`", col)
            if referenced == number or referenced in seen:
                continue
            seen.add(referenced)
            linked = any(
                link.text_start <= match.start() and match.end() <= link.text_end and resolve(path, link.dest) == target
                for link in links_by_line.get(lineno, [])
            )
            if not linked:
                relative = os.path.relpath(target, path.parent)
                if not relative.startswith("."):
                    relative = f"./{relative}"
                report.error(
                    lineno,
                    "markdown-link-first",
                    f"the first reference to {canonical} must be a relative link: `[{canonical}]({relative})`",
                    col,
                )


def check_rfc2119(report: Report, body: Body) -> None:
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
            report.error(
                lineno,
                "markdown-rfc2119",
                f"the RFC 2119 keyword `{match.group(0)}` must only be used in the Specification section",
                match.start() + 1,
            )
