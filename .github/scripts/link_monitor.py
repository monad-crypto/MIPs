#!/usr/bin/env python3
"""
Scheduled link monitor for the MIPs repo (Job 2).

Scope: the MIPs repo content and the Monad forum threads that discuss each
proposal (NOT the wider internet). It:

  1. discovers every MIP/MRC forum thread (from `discussions-to:` front matter
     and from the forum's MIPs category listing),
  2. scans every post in each thread for links back to `mips.monad.xyz` or
     `github.com/monad-crypto/MIPs` and status-checks them,
  3. status-checks the `mips.monad.xyz` / `github.com/monad-crypto/MIPs` links
     that appear in the repo's own markdown (resolved against the live site),

and writes a report. When run in GitHub Actions with a token it opens/updates a
tracking issue; otherwise it just prints the report.

This job is a MONITOR: it never fails the build. Forum posts are not part of any
PR and cannot be fixed by a PR author, so this must not gate merges.
"""
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

FORUM = "https://forum.monad.xyz"
CATEGORY_JSON = f"{FORUM}/c/mips/8.json"
SITE = "https://mips.monad.xyz"
REPO = "monad-crypto/MIPs"

TARGET_RE = re.compile(r"(mips\.monad\.xyz|github\.com/monad-crypto/MIPs)", re.I)
HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)
URL_RE = re.compile(r'https?://[^\s"\'<>\)\]]+', re.I)
FM_DISCUSS_RE = re.compile(r"^discussions-to:\s*(\S+)\s*$", re.I | re.M)

_CTX = ssl.create_default_context()
UA = {"User-Agent": "monad-mips-link-monitor/1.0 (+https://mips.monad.xyz)"}


def fetch(url, tries=3, timeout=30):
    """Return (status, final_url, body_text). status is int or 'ERR:<name>'."""
    last = None
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            r = urllib.request.urlopen(req, timeout=timeout, context=_CTX)
            return r.status, r.geturl(), r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            code = e.code
            if code == 429 or 500 <= code < 600:
                last = code
                time.sleep(2 * (attempt + 1))
                continue
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            return code, getattr(e, "url", url), body
        except Exception as e:  # noqa: BLE001
            last = f"ERR:{type(e).__name__}"
            time.sleep(1 + attempt)
    return last if last is not None else "ERR:Unknown", url, ""


def status_only(url):
    s, _final, _body = fetch(url)
    return s


def is_dead(status):
    return isinstance(status, int) and status in (404, 410)


def is_unreachable(status):
    return (not isinstance(status, int)) or status >= 500 or status == 429


# --------------------------------------------------------------------------- #
# 1. Discover forum threads
# --------------------------------------------------------------------------- #
def thread_ids_from_frontmatter(root="."):
    ids = set()
    for base in ("MIPs", "MRCs"):
        d = os.path.join(root, base)
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if not name.endswith(".md"):
                continue
            with open(os.path.join(d, name), encoding="utf-8") as fh:
                text = fh.read()
            m = FM_DISCUSS_RE.search(text)
            if not m:
                continue
            url = m.group(1).strip().strip("<>")
            tid = _topic_id_from_url(url)
            if tid:
                ids.add(tid)
    return ids


def _topic_id_from_url(url):
    """Extract numeric topic id from a forum URL, resolving slug-only URLs."""
    m = re.search(r"/t/[^/]+/(\d+)", url)
    if m:
        return int(m.group(1))
    m = re.search(r"/t/(\d+)", url)
    if m:
        return int(m.group(1))
    # slug-only URL (e.g. .../t/mip-1-...): resolve via its .json
    if "/t/" in url:
        s, _f, body = fetch(url.rstrip("/") + ".json")
        if isinstance(s, int) and s == 200:
            try:
                return int(json.loads(body).get("id"))
            except Exception:  # noqa: BLE001
                return None
    return None


def thread_ids_from_category():
    ids = set()
    url = CATEGORY_JSON
    for _ in range(20):  # page cap
        s, _f, body = fetch(url)
        if not (isinstance(s, int) and s == 200):
            break
        data = json.loads(body)
        tl = data.get("topic_list", {})
        for t in tl.get("topics", []):
            tid = t.get("id")
            if tid:
                ids.add(int(tid))
        more = tl.get("more_topics_url")
        if not more:
            break
        # more_topics_url looks like /c/mips/8?page=1 ; force .json
        more = more.replace("?", ".json?") if ".json" not in more else more
        url = urllib.parse.urljoin(FORUM, more)
        time.sleep(0.5)
    return ids


# --------------------------------------------------------------------------- #
# 2. Scan thread posts for target links
# --------------------------------------------------------------------------- #
def scan_thread(tid):
    """Return (title, [ (post_no, username, url, status) ]) for dead target links."""
    s, _f, body = fetch(f"{FORUM}/t/{tid}.json")
    if not (isinstance(s, int) and s == 200):
        return None, [], f"fetch status {s}"
    data = json.loads(body)
    title = data.get("title", f"topic {tid}")
    stream = data.get("post_stream", {})
    posts = list(stream.get("posts", []))
    have = {p["id"] for p in posts}
    missing = [i for i in stream.get("stream", []) if i not in have]
    for i in range(0, len(missing), 40):
        chunk = missing[i : i + 40]
        q = "&".join(f"post_ids%5B%5D={pid}" for pid in chunk)
        s2, _f2, b2 = fetch(f"{FORUM}/t/{tid}/posts.json?{q}")
        if isinstance(s2, int) and s2 == 200:
            posts.extend(json.loads(b2).get("post_stream", {}).get("posts", []))
        time.sleep(0.3)

    seen, dead = set(), []
    for p in posts:
        cooked = p.get("cooked", "")
        cand = set(HREF_RE.findall(cooked))
        cand |= {u.rstrip(".,);'\"") for u in URL_RE.findall(cooked)}
        for raw in cand:
            absu = urllib.parse.urldefrag(
                urllib.parse.urljoin(f"{FORUM}/t/{tid}", raw)
            )[0]
            if not TARGET_RE.search(absu):
                continue
            key = (p.get("post_number"), absu)
            if key in seen:
                continue
            seen.add(key)
            st = status_only(absu)
            if is_dead(st):
                dead.append((p.get("post_number"), p.get("username"), absu, st))
        time.sleep(0.05)
    return title, dead, None


# --------------------------------------------------------------------------- #
# 3. Scan repo markdown for target links (checked against the live site)
# --------------------------------------------------------------------------- #
def scan_repo_markdown(root="."):
    dead = []
    md_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        if "/.git" in dirpath or dirpath.endswith("/.git"):
            continue
        for fn in filenames:
            if fn.endswith(".md"):
                md_files.append(os.path.join(dirpath, fn))
    for path in sorted(md_files):
        rel = os.path.relpath(path, root)
        # the URL a file maps to on the live site (permalink: /:path, no ext)
        page_url = SITE + "/" + re.sub(r"\.md$", "", rel) if rel.startswith(("MIPs/", "MRCs/")) else SITE + "/"
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        # markdown links [txt](url) and bare urls
        cand = set(re.findall(r"\]\(([^)]+)\)", text))
        cand |= set(URL_RE.findall(text))
        checked = set()
        for raw in cand:
            raw = raw.strip().split(" ")[0].rstrip(".,);'\"")
            absu = urllib.parse.urldefrag(urllib.parse.urljoin(page_url, raw))[0]
            if not TARGET_RE.search(absu) or absu in checked:
                continue
            checked.add(absu)
            st = status_only(absu)
            if is_dead(st):
                dead.append((rel, absu, st))
            time.sleep(0.05)
    return dead


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def build_report(forum_dead, repo_dead, unreachable):
    lines = []
    total = sum(len(v[1]) for v in forum_dead.values()) + len(repo_dead)
    when = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    lines.append(f"**MIPs link monitor** — {when}")
    lines.append("")
    if total == 0:
        lines.append("✅ No dead links found in forum threads or repo markdown.")
    else:
        lines.append(f"🔴 **{total} dead link(s) found.**")
    if repo_dead:
        lines.append("")
        lines.append("### Repo markdown → dead links (on the live site)")
        for rel, url, st in repo_dead:
            lines.append(f"- `{rel}` → {url} — {st}")
    printed_header = False
    for tid, (title, dead, err) in forum_dead.items():
        if not dead:
            continue
        if not printed_header:
            lines.append("")
            lines.append("### Forum threads → dead links in posts")
            printed_header = True
        lines.append(f"- **{title}** ({FORUM}/t/{tid})")
        for pn, user, url, st in dead:
            lines.append(f"    - post #{pn} (@{user}): {url} — {st}")
    if unreachable:
        lines.append("")
        lines.append("### ⚠️ Unverified (timeout / 5xx / rate-limited — not counted as dead)")
        for ctx, url, st in unreachable:
            lines.append(f"- {ctx}: {url} — {st}")
    return "\n".join(lines), total


# --------------------------------------------------------------------------- #
# GitHub issue upsert
# --------------------------------------------------------------------------- #
def gh_api(method, path, token, payload=None):
    url = f"https://api.github.com{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "monad-mips-link-monitor",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        r = urllib.request.urlopen(req, timeout=30, context=_CTX)
        return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def upsert_issue(report, has_findings, token):
    label = "link-monitor"
    gh_api("POST", f"/repos/{REPO}/labels", token,
           {"name": label, "color": "d73a4a",
            "description": "Automated dead-link monitor"})
    st, issues = gh_api("GET", f"/repos/{REPO}/issues?labels={label}&state=open", token)
    existing = issues[0] if isinstance(issues, list) and issues else None
    title = "🔗 Dead-link monitor report"
    body = report + "\n\n_Auto-generated by `.github/workflows/link-monitor.yml`._"
    if existing:
        num = existing["number"]
        gh_api("PATCH", f"/repos/{REPO}/issues/{num}", token, {"title": title, "body": body})
        gh_api("POST", f"/repos/{REPO}/issues/{num}/comments", token, {"body": report})
        print(f"Updated issue #{num}")
    elif has_findings:
        st2, created = gh_api("POST", f"/repos/{REPO}/issues", token,
                              {"title": title, "body": body, "labels": [label]})
        print(f"Created issue: {created.get('number') if isinstance(created, dict) else created}")
    else:
        print("No findings and no open issue — nothing to do.")


def main():
    root = os.environ.get("REPO_ROOT", ".")
    print("Discovering forum threads...")
    ids = thread_ids_from_frontmatter(root) | thread_ids_from_category()
    print(f"  {len(ids)} threads: {sorted(ids)}")

    forum_dead = {}
    for tid in sorted(ids):
        title, dead, err = scan_thread(tid)
        forum_dead[tid] = (title or f"topic {tid}", dead, err)
        tag = f"{len(dead)} dead" if dead else "clean"
        print(f"  t/{tid}: {title!r} -> {tag}" + (f" (err: {err})" if err else ""))
        time.sleep(0.3)

    print("Scanning repo markdown...")
    repo_dead = scan_repo_markdown(root)
    print(f"  {len(repo_dead)} dead target links in repo markdown")

    report, total = build_report(forum_dead, repo_dead, [])
    print("\n" + "=" * 70 + "\n" + report + "\n" + "=" * 70)

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report + "\n")

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        upsert_issue(report, total > 0, token)
    else:
        print("\n(No GITHUB_TOKEN — skipping issue upsert.)")

    # Monitor never fails the build.
    return 0


if __name__ == "__main__":
    sys.exit(main())
