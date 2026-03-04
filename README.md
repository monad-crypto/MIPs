# Monad Improvement Proposals (MIPs)

This repository builds a static MIP website with Jekyll and deploys it with GitHub Pages.

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
