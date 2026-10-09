"""
Markdown scanning. Fenced code, inline code, HTML comments and link targets
are blanked out so that rules can scan prose by column.
"""

import re
from dataclasses import dataclass
from urllib.parse import SplitResult, urlsplit

ALLOWED_HTML_TAGS = {"sup", "sub"}

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
HEADING_NO_SPACE_RE = re.compile(r"^ {0,3}#{1,6}[^#\s]")
# Possessive quantifiers keep matching linear on adversarial input; they
# need Python 3.11 or newer.
LINK_LABEL = r"((?:[^\[\]]|\[[^\[\]]*+\])*+)"
LINK_DEST = r"((?:[^\s<>()]|\([^\s<>()]*+\))*+)"
LINK_TITLE = r"(?:\s++(?:\"[^\"]*+\"|'[^']*+'))?+"
INLINE_LINK_RE = re.compile(r"(!?)\[" + LINK_LABEL + r"\]\(\s*+<?" + LINK_DEST + r">?" + LINK_TITLE + r"\s*+\)")
REF_LINK_RE = re.compile(r"(!?)\[" + LINK_LABEL + r"\]\[([^\]]*+)\]")
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]++)\]:\s*+<?(\S+?)>?" + LINK_TITLE + r"\s*+$")
AUTOLINK_RE = re.compile(r"<(https?://[^\s>]+)>", re.IGNORECASE)
# Browsers accept `/` in place of whitespace before attributes and let a tag
# continue on the next line, so a tag is recognised by its name alone.
HTML_TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9-]*)(?=[\s/>]|$)")
KRAMDOWN_RE = re.compile(r"\{:")


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


def split_url(dest: str) -> SplitResult:
    # Browsers read a backslash as a slash, so `/\evil.example` is a
    # scheme-relative URL.
    return urlsplit(dest.replace("\\", "/"))


class Body:
    def __init__(self, lines: list[str], first_line: int):
        self.lines = lines
        self.first_line = first_line
        self.headings: list[Heading] = []
        self.links: list[Link] = []
        self.comments: list[tuple[int, int]] = []
        self.headings_without_space: list[int] = []
        self.html_tags: list[tuple[int, int, str]] = []
        self.kramdown: list[tuple[int, int]] = []
        self.unclosed_fence: int | None = None
        self.unparsed_links: list[tuple[int, int]] = []
        self.prose: list[tuple[int, str]] = []
        self._scan()

    def _scan(self) -> None:
        refs = self._reference_definitions(self.lines)
        fence: tuple[str, int, int] | None = None
        in_comment = False
        for offset, raw in enumerate(self.lines):
            lineno = self.first_line + offset
            if fence:
                if re.match(rf"^ {{0,3}}{re.escape(fence[0])}{{{fence[1]},}}[ \t]*$", raw):
                    fence = None
                continue
            opening = FENCE_RE.match(raw)
            if opening and not in_comment:
                fence = (opening.group(1)[0], len(opening.group(1)), lineno)
                continue
            text, in_comment = self._blank_comments(raw, lineno, in_comment)
            text = blank_code_spans(text)
            for tag in HTML_TAG_RE.finditer(text):
                bare = text[tag.end() : tag.end() + 1] == ">"
                if not (bare and tag.group(1).lower() in ALLOWED_HTML_TAGS):
                    self.html_tags.append((lineno, tag.start() + 1, tag.group(0)))
            for attributes in KRAMDOWN_RE.finditer(text):
                self.kramdown.append((lineno, attributes.start() + 1))
            if HEADING_NO_SPACE_RE.match(text):
                self.headings_without_space.append(lineno)
            heading = HEADING_RE.match(text)
            if heading:
                self.headings.append(Heading(lineno, len(heading.group(1)), (heading.group(2) or "").strip()))
            text = self._extract_links(text, lineno, refs)
            self.prose.append((lineno, text))
        if fence:
            self.unclosed_fence = fence[2]

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
        text = AUTOLINK_RE.sub(autolink, text)
        # kramdown nests brackets in link text to any depth and allows
        # whitespace in a `<url>`; whatever the patterns above did not
        # consume is reported rather than let through.
        for unparsed in re.finditer(r"\]\(", text):
            self.unparsed_links.append((lineno, unparsed.start() + 1))
        return text
