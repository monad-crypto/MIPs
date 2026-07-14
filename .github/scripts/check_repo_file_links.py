#!/usr/bin/env python3
"""
Offline validator for links that point at files inside THIS repo.

For every `github.com/monad-crypto/MIPs/blob|tree/<ref>/<path>` (and the
equivalent `raw.githubusercontent.com/...`) link found in the repo's markdown,
assert that `<path>` actually exists in the checked-out tree, matching case
exactly. This catches wrong-case references such as `.../MIPS/MIP-4.md` (the
folder is `MIPs`) deterministically.

Exit code is non-zero if any referenced path is missing.
"""
import os
import re
import sys

REPO_SLUG = "monad-crypto/MIPs"
LINK_RE = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/"
    + re.escape(REPO_SLUG)
    + r"/(?:blob|tree)/[^/\s]+/([^\s)\"'>#?]+)",
    re.I,
)
RAW_RE = re.compile(
    r"(?:https?://)?raw\.githubusercontent\.com/"
    + re.escape(REPO_SLUG)
    + r"/[^/\s]+/([^\s)\"'>#?]+)",
    re.I,
)


def exists_exact(root, relpath):
    """True iff relpath exists under root with every component matching case."""
    relpath = relpath.strip("/")
    if not relpath:
        return True  # link to a ref root (e.g. tree/main) is fine
    current = root
    for part in relpath.split("/"):
        try:
            entries = os.listdir(current)
        except (FileNotFoundError, NotADirectoryError):
            return False
        if part not in entries:
            return False
        current = os.path.join(current, part)
    return True


def markdown_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules", "vendor", "_site")]
        for fn in filenames:
            if fn.endswith(".md"):
                yield os.path.join(dirpath, fn)


def main():
    root = os.environ.get("REPO_ROOT", ".")
    problems = []
    checked = 0
    for path in sorted(markdown_files(root)):
        rel = os.path.relpath(path, root)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        targets = set()
        for m in LINK_RE.finditer(text):
            targets.add(m.group(1))
        for m in RAW_RE.finditer(text):
            targets.add(m.group(1))
        for target in sorted(targets):
            checked += 1
            if not exists_exact(root, target):
                problems.append((rel, target))

    if problems:
        print(f"❌ {len(problems)} in-repo GitHub link(s) point to a path that "
              f"does not exist in the tree (checked {checked}):\n")
        for rel, target in problems:
            print(f"  - {rel}: github.com/{REPO_SLUG}/blob/<ref>/{target}")
        print("\nMost commonly this is a case mismatch (e.g. `MIPS/` vs `MIPs/`) "
              "or a moved/renamed file.")
        return 1

    print(f"✅ All {checked} in-repo GitHub file links resolve to real paths "
          f"(case-sensitive).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
