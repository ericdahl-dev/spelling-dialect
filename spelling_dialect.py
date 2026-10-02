#!/usr/bin/env python3
"""spelling: skip-file (the word tables below hold both spellings by design)

spelling-dialect: keep a repo in one English spelling, American or British.

    spelling_dialect.py [--dialect american|british|british-oxford] [--scope all|docs] [PATH ...]

With no PATH, or one directory, checks every file git tracks there. With files (as pre-commit
passes them), checks just those. Prints `file:line: word -> fix` and exits 1 if anything is found.

Dialects:
  american        color, center, canceled, analyze, organize, gray
  british         colour, centre, cancelled, analyse, organise
  british-oxford  colour, centre, cancelled, analyse, but organize (Oxford spelling keeps -ize)

Words are checked one by one, including inside identifiers (colour_edges, AudioAnalyser,
scanCancelled). British modes skip American spellings that are also correct British (a computer
program, a gas meter, to check, a judgment), and by default check docs only (Markdown, text):
code is full of American APIs (CSS color, initialize, serialize) that a British repo can't rename.

Exceptions:
  a line         add "spelling: ok" to it
  a file         put "spelling: skip-file" in its first five lines
  a repo         a .spelling-dialect file at the root:
                     dialect: british        # default dialect for this repo
                     scope: all              # all (default for american) | docs (default for british)
                     cancelled               # an allowed word, e.g. a stored value or an API name
                     path: vendor/           # skip files under this path
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

DIALECTS = ("american", "british", "british-oxford")

# (british, american, kind). Kind "ise" marks the -ise/-ize words Oxford spelling writes with -ize.
PAIRS: list[tuple[str, str, str]] = []


def _add(brit: str, amer: str, kind: str = "word") -> None:
    PAIRS.append((brit, amer, kind))


for w in ["colour", "neighbour", "behaviour", "favour", "honour", "labour", "flavour", "humour", "rumour", "harbour",
          "vapour", "armour", "endeavour", "odour", "parlour", "savour"]:
    for end in ["", "s", "ed", "ing", "ful", "less", "able", "ite", "ites"]:
        _add(w + end, w.replace("our", "or") + end)
_add("favourite", "favorite"), _add("favourites", "favorites"), _add("colourise", "colorize", "ise")
for w in ["centre", "metre", "litre", "fibre", "theatre", "calibre", "sombre", "spectre", "lustre", "millimetre",
          "centimetre", "kilometre", "micrometre", "nanometre", "millilitre", "centilitre", "decilitre"]:
    stem = w[:-2]
    _add(w, stem + "er"), _add(w + "s", stem + "ers"), _add(w + "d", stem + "ered")
for stem in ["organis", "recognis", "realis", "normalis", "minimis", "maximis", "optimis", "visualis", "prioritis",
             "initialis", "serialis", "deserialis", "summaris", "synchronis", "customis", "categoris", "finalis",
             "stabilis", "rasteris", "centralis", "utilis", "apologis", "standardis", "specialis", "authoris",
             "capitalis", "digitis", "localis", "memoris", "quantis", "randomis", "sanitis", "tokenis", "vectoris",
             "characteris", "parameteris", "generalis", "materialis", "criticis", "equalis", "polaris", "regularis",
             "binaris", "linearis", "discretis", "parallelis"]:
    for end in ["e", "es", "ed", "ing", "ation", "ations", "er", "ers"]:
        _add(stem + end, stem[:-1] + "z" + end, "ise")
for end in ["e", "es", "ed", "ing"]:  # not "emphasis(es)": nouns in both
    if end != "es":
        _add("emphasis" + end, "emphasiz" + end, "ise")
for stem, amer in {"analys": "analyz", "paralys": "paralyz", "catalys": "catalyz"}.items():
    for end in ["e", "ed", "ing", "er", "ers"]:  # not "analyses": also the plural of "analysis"
        _add(stem + end, amer + end)
for base in ["cancel", "label", "model", "travel", "level", "signal", "channel", "total", "fuel", "marshal", "tunnel",
             "funnel", "dial", "pedal", "rival"]:
    for end in ["ed", "ing", "er", "ers"]:
        _add(base + "l" + end, base + end)
for brit, amer in {"grey": "gray", "greys": "grays", "greyed": "grayed", "whilst": "while", "amongst": "among",
                   "learnt": "learned", "spelt": "spelled", "programme": "program", "programmes": "programs",
                   "catalogue": "catalog", "catalogues": "catalogs", "licence": "license", "licences": "licenses",
                   "defence": "defense", "offence": "offense", "judgement": "judgment", "acknowledgement": "acknowledgment",
                   "acknowledgements": "acknowledgments", "ageing": "aging", "artefact": "artifact", "artefacts": "artifacts",
                   "aluminium": "aluminum", "sceptical": "skeptical", "tyre": "tire", "tyres": "tires", "cheque": "check",
                   "cheques": "checks", "storey": "story", "storeys": "stories", "mould": "mold", "plough": "plow",
                   "manoeuvre": "maneuver", "aeroplane": "airplane", "cosy": "cozy", "enrol": "enroll", "fulfil": "fulfill",
                   "counsellor": "counselor", "jewellery": "jewelry", "speciality": "specialty", "analogue": "analog",
                   "dialogue": "dialog"}.items():
    _add(brit, amer)

# American spellings that are also standard British: British modes never flag them.
ALSO_BRITISH = {"program", "programs", "meter", "meters", "check", "checks", "license", "licensed", "practice",
                "judgment", "analog", "story", "stories", "tire", "tires", "gray", "grays", "mold", "artifact",
                "artifacts", "dialog", "aging", "enroll", "fulfill", "while", "among", "learned", "spelled", "defense"}
# British spellings that are also standard American: American mode never flags them.
ALSO_AMERICAN = {"dialogue", "analogue"}

# Platform APIs spelled British by definition: Web Audio, Python asyncio, Swift concurrency, Foundation.
WEB_APIS = ["AnalyserNode", "createAnalyser", "CancelledError", "isCancelled", "NSURLErrorCancelled"]
# GitHub Actions spells its own job/run result "cancelled" (and the cancelled() function).
WORKFLOW_DIR, WORKFLOW_WORDS = ".github/workflows/", {"cancelled"}
LINE_MARKER, FILE_MARKER = "spelling: ok", "spelling: skip-file"
WORD = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")  # splits identifiers: colour_edges, scanCancelled, AudioAnalyser
DOCS = {".md", ".markdown", ".txt", ".rst", ".adoc", ".mdx"}
TEXT = DOCS | {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte", ".html", ".erb", ".css", ".scss",
               ".toml", ".yml", ".yaml", ".json", ".cfg", ".ini", ".go", ".rb", ".rake", ".swift", ".c", ".h", ".cpp",
               ".hpp", ".cc", ".ino", ".rs", ".java", ".kt", ".sh", ".lua", ".sql", ""}
ALWAYS_SKIP = ("node_modules/", "vendor/bundle/", "dist/", "build/", ".min.")
LOCKFILES = ("package-lock.json", "uv.lock", "yarn.lock", "pnpm-lock.yaml", "Gemfile.lock", "go.sum", "Cargo.lock")
CONFIG, LEGACY_CONFIG = ".spelling-dialect", ".american-spelling-allow"


def wrong_spellings(dialect: str) -> dict[str, str]:
    """Word (lowercase) -> preferred spelling, for words the dialect rejects."""
    if dialect == "american":
        return {b: a for b, a, _ in PAIRS if b not in ALSO_AMERICAN}
    out = {a: b for a, b in ((a, b) for b, a, _ in PAIRS) if a not in ALSO_BRITISH}
    if dialect == "british-oxford":  # -ize is correct; -ise is what's wrong
        for b, a, kind in PAIRS:
            if kind == "ise":
                out.pop(a, None)
                out[b] = a
    return out


def check_text(text: str, dialect: str = "american", allowed: set[str] = frozenset()) -> list[tuple[int, str, str]]:
    """(line number, word as written, preferred spelling) for each word the dialect rejects."""
    wrong = wrong_spellings(dialect)
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if LINE_MARKER in line:
            continue
        for name in WEB_APIS:
            line = line.replace(name, " ")
        for word in WORD.findall(line):
            fix = wrong.get(word.lower())
            if fix and word.lower() not in allowed:
                hits.append((n, word, fix))
    return hits


def read_config(root: Path) -> dict:
    config = {"dialect": None, "scope": None, "words": set(), "paths": []}
    for name in (CONFIG, LEGACY_CONFIG):
        try:
            lines = (root / name).read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            continue
        for line in lines:
            line = line.split("#", 1)[0].strip()
            key, _, value = line.partition(":")
            if key in ("dialect", "scope", "path") and value.strip():
                if key == "path":
                    config["paths"].append(value.strip())
                else:
                    config[key] = value.strip()
            elif line:
                config["words"].add(line.lower())
    return config


def check_repo(root, dialect: str | None = None, scope: str | None = None, files: list[str] | None = None) -> list[str]:
    root = Path(root)
    config = read_config(root)
    dialect = dialect or config["dialect"] or "american"
    if dialect not in DIALECTS:
        raise SystemExit(f"Unknown dialect {dialect!r}: use one of {', '.join(DIALECTS)}")
    scope = scope or config["scope"] or ("all" if dialect == "american" else "docs")
    if files is None:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, check=True).stdout
        files = [f for f in listed.split("\0") if f]
    problems = []
    for name in files:
        path = root / name
        suffix = path.suffix.lower()
        if (
            Path(name).name in (CONFIG, LEGACY_CONFIG)
            or suffix not in (DOCS if scope == "docs" else TEXT)
            or name.endswith(LOCKFILES)
            or any(part in name for part in ALWAYS_SKIP)
            or any(name.startswith(p) for p in config["paths"])
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        if FILE_MARKER in "\n".join(text.splitlines()[:5]):
            continue
        allowed = config["words"] | (WORKFLOW_WORDS if name.startswith(WORKFLOW_DIR) else set())
        problems += [f"{name}:{n}: {word} -> {fix}" for n, word, fix in check_text(text, dialect, allowed)]
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Keep a repo in one English spelling, American or British.")
    parser.add_argument("--dialect", choices=DIALECTS, help="default: the repo's .spelling-dialect, else american")
    parser.add_argument("--scope", choices=("all", "docs"), help="default: all for american, docs for british")
    parser.add_argument("paths", nargs="*", help="a repo directory (default .) or files to check")
    args = parser.parse_args(argv)
    paths = args.paths or ["."]
    if len(paths) == 1 and Path(paths[0]).is_dir():
        root, files = Path(paths[0]), None
    else:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
        root = Path(top or ".")
        files = [str(Path(p).resolve().relative_to(root.resolve())) for p in paths]
    found = check_repo(root, args.dialect, args.scope, files)
    dialect = args.dialect or read_config(root)["dialect"] or "american"
    print("\n".join(found) or f"Spelling ({dialect}): OK")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
