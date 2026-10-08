# Monad Improvement Proposals (MIPs)

This repository builds a static MIP website with Jekyll and is intended to be deployed with GitHub Pages (deployment may currently be disabled in CI).

## Build locally

### Prerequisites

- Ruby `>= 3.1` (including Ruby `4.x`)
- Bundler (`gem install bundler`)

### Install dependencies

```sh
bundle install
```

### Run locally

```sh
bundle exec jekyll serve
```

Then open <http://localhost:4000>.

### Production-style build

```sh
JEKYLL_ENV=production bundle exec jekyll build
```

Generated files are in `_site/`.

## Math

Use `$$...$$` for inline math. For display math, put the opening and closing `$$` on separate lines, with blank lines around the block. Kramdown converts both forms to MathJax delimiters.

Use `\lvert V \rvert` instead of `|V|` inside inline math so Markdown does not interpret the vertical bars as table separators.

## Linting

Every pull request runs `scripts/lint_mips.py` on the MIPs and MRCs it changes. The linter checks the preamble, the section layout, links and proposal references against the rules in [MIP-1](MIPs/MIP-1.md). It needs Python 3 and the pinned PyYAML (`pip install -r scripts/requirements.txt`).

Lint every proposal:

```sh
python3 scripts/lint_mips.py
```

Lint specific files:

```sh
python3 scripts/lint_mips.py MIPs/MIP-7.md MRCs/MRC-13.md
```

Run the linter's own tests:

```sh
python3 -m unittest discover scripts
```
