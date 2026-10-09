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

import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

from mip_linter.body import check_links, check_markup, check_mentions, check_rfc2119, check_sections
from mip_linter.findings import Finding, Report
from mip_linter.markdown import Body
from mip_linter.preamble import check_preamble
from mip_linter.repo import Repo

MAX_FILE_BYTES = 1_000_000
MAX_LINE_LENGTH = 10_000
# MIP-1 describes the process itself and does not follow the template.
TEMPLATE_EXEMPT = {"MIPs/MIP-1.md"}

NON_PRINTABLE_RE = re.compile(r"[^\t\x20-\x7e]")
INVISIBLE_CATEGORIES = {"Cc", "Cf", "Co", "Zl", "Zp"}


class DocumentLinter:
    def __init__(self, path: Path, repo: Repo):
        self.path = path
        self.repo = repo
        try:
            display = str(path.resolve().relative_to(Path.cwd()))
        except ValueError:
            display = str(path)
        self.report = Report(display)
        try:
            self.repo_path: str | None = path.resolve().relative_to(repo.root).as_posix()
        except ValueError:
            self.repo_path = None

    def lint(self) -> list[Finding]:
        try:
            self._lint()
        except UnicodeDecodeError:
            self.report.error(1, "file-encoding", "the file is not valid UTF-8")
        except OSError as exc:
            self.report.error(1, "file-unreadable", f"the file cannot be read: {exc.strerror}")
        except Exception as exc:
            # Last resort, so that one document cannot abort the whole run.
            self.report.error(1, "lint-failed", f"the linter failed on this file: {type(exc).__name__}: {exc}")
        return self.report.findings

    def _lint(self) -> None:
        lines = self.read_lines()
        if lines is None:
            return
        if not lines or lines[0] != "---":
            self.report.error(1, "preamble-missing", "the document must start with a `---` preamble")
            return
        try:
            end = lines.index("---", 1)
        except ValueError:
            self.report.error(1, "preamble-missing", "the preamble is not closed with `---`")
            return
        preamble = check_preamble(self.report, lines[1:end], self.path, self.repo)
        body = Body(lines[end + 1 :], end + 2)
        check_markup(self.report, body)
        check_mentions(self.report, body, self.path, self.repo, preamble.number)
        if self.repo_path in TEMPLATE_EXEMPT:
            return
        check_sections(self.report, body, preamble)
        check_links(self.report, body, self.path, self.repo)
        check_rfc2119(self.report, body)

    def read_lines(self) -> list[str] | None:
        if self.path.stat().st_size > MAX_FILE_BYTES:
            self.report.error(1, "file-size", f"the file must be smaller than {MAX_FILE_BYTES // 1_000_000} MB")
            return None
        with self.path.open(encoding="utf-8", newline="") as handle:
            text = handle.read()
        if "\r" in text:
            self.report.error(text.count("\n", 0, text.index("\r")) + 1, "text-line-endings", "lines must end with LF, not CR or CRLF")
            text = text.replace("\r\n", "\n").replace("\r", "\n")
        # str.splitlines also splits on U+2028, U+0085 and form feed, which
        # kramdown keeps inside the line.
        lines = text.split("\n")
        if lines[-1] == "":
            lines.pop()
        for lineno, line in enumerate(lines, start=1):
            for match in NON_PRINTABLE_RE.finditer(line):
                if unicodedata.category(match.group(0)) in INVISIBLE_CATEGORIES:
                    self.report.error(
                        lineno,
                        "text-invisible-chars",
                        f"invisible, formatting or control character U+{ord(match.group(0)):04X} is not allowed",
                        match.start() + 1,
                    )
        long_lines = [lineno for lineno, line in enumerate(lines, start=1) if len(line) > MAX_LINE_LENGTH]
        for lineno in long_lines:
            self.report.error(lineno, "line-length", f"lines must be at most {MAX_LINE_LENGTH} characters long")
        return None if long_lines else lines


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
