<!-- spelling: skip-file (this README shows both spellings on purpose) -->
# spelling-dialect

Keep a repo in **one English spelling**: American (`color`, `center`, `canceled`) or British (`colour`, `centre`, `cancelled`).

```
README.md:12: colour -> color
src/render.ts:40: Colour -> color      (inside setColourMode)
engine/scan.py:88: cancelled -> canceled
```

- **Inside identifiers too.** `colour_edges`, `AudioAnalyser` and `scanCancelled` are split into words, so an inconsistent name is caught, not just prose.
- **American, British or Oxford.** British mode doesn't flag American spellings that are also correct British (a computer *program*, a gas *meter*, to *check*, a *judgment*). Oxford mode (`british-oxford`) keeps `-ize`.
- **Made for real repos.** Allow words you don't control (a stored `"cancelled"` status, a third-party API), skip vendored paths, or opt out a single line or file.
- **No dependencies.** One Python file, standard library only.

## GitHub Action

```yaml
name: Spelling
on: [pull_request]
jobs:
  spelling:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: ericdahl-dev/spelling-dialect@v1
        with:
          dialect: american   # or british, british-oxford (default: the repo's .spelling-dialect, else american)
```

Inputs: `dialect`, `scope` (`all` or `docs`), `path` (default `.`).

## pre-commit

```yaml
repos:
  - repo: https://github.com/ericdahl-dev/spelling-dialect
    rev: v1.0.0
    hooks:
      - id: spelling-dialect
        # args: [--dialect, british]
```

## Command line

```bash
pipx run --spec git+https://github.com/ericdahl-dev/spelling-dialect spelling-dialect .
# or just the file:
python3 spelling_dialect.py --dialect british path/to/repo
```

It checks every file git tracks (skipping lockfiles, `node_modules/`, `dist/`, `build/`), prints `file:line: word -> fix`, and exits 1 if anything is found.

## Configuration: `.spelling-dialect`

Put this at the root of the repo:

```
dialect: british     # american (default) | british | british-oxford
scope: all           # all (default for american) | docs (default for british)

# Words to allow, e.g. a value stored in your database or an API's field name.
# Matched case-insensitively, also inside identifiers.
cancelled

# Paths to skip, e.g. vendored code.
path: vendor/
path: lib/unity/
```

Why British mode checks only docs by default: code is full of American spellings no repo can rename, like CSS `color` and `center`, Ruby's `initialize`, and `serialize` in every library. Set `scope: all` if your code is British throughout.

### One line or one file

- A line: add `spelling: ok` anywhere on it, e.g. `status == "cancelled"  # spelling: ok (GitHub's value)`.
- A file: put `spelling: skip-file` in its first five lines.

Platform APIs that are British by definition are always allowed: Web Audio's `AnalyserNode` and `createAnalyser`, and Python's `CancelledError`.

## What it knows

| Pattern | American | British |
|---|---|---|
| -or / -our | color, behavior, favorite | colour, behaviour, favourite |
| -er / -re | center, fiber, theater | centre, fibre, theatre |
| -ize / -ise | organize, normalize | organise, normalise (Oxford: organize) |
| -yze / -yse | analyze, paralyze | analyse, paralyse |
| -l / -ll | canceled, labeled, modeling | cancelled, labelled, modelling |
| others | gray, catalog, license (noun), defense, judgment, aluminum, aging | grey, catalogue, licence, defence, judgement, aluminium, ageing |

It's a word list, not a dictionary: it won't catch every difference, and it won't flag words that are standard in both dialects (`dialogue`, the plural `analyses`).

## How it compares

- [`misspell -locale US`](https://github.com/golangci/misspell) flags common British spellings in text, but not inside identifiers, and it has no allowlist for stored values.
- [cspell](https://cspell.org/) with an `en-US` dictionary is a full spell checker. Use it if you want typo checking as well; it takes more setup.

## License

MIT
