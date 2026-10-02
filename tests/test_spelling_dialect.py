# spelling: skip-file (this file contains the spellings it tests for)
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from spelling_dialect import check_repo, check_text


def words(text, dialect="american", allowed=()):
    return [(w, fix) for _, w, fix in check_text(text, dialect, set(allowed))]


def repo(files):
    root = Path(tempfile.mkdtemp())
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


class American(unittest.TestCase):
    def test_flags_british_spellings_with_fixes(self):
        self.assertEqual(
            words("colour centre cancelled analysed normalise grey catalogue"),
            [("colour", "color"), ("centre", "center"), ("cancelled", "canceled"), ("analysed", "analyzed"),
             ("normalise", "normalize"), ("grey", "gray"), ("catalogue", "catalog")],
        )

    def test_looks_inside_identifiers(self):
        self.assertEqual([w for w, _ in words("colour_edges AudioAnalyser scanCancelled")], ["colour", "Analyser", "Cancelled"])

    def test_leaves_american_text_and_lookalikes_alone(self):
        self.assertEqual(words("color center canceled noise raise precise exercise cancellation emphasis"), [])

    def test_analyses_is_also_the_plural_of_analysis(self):
        self.assertEqual(words("Run all analyses."), [])

    def test_platform_api_names_spelled_british_are_allowed(self):
        self.assertEqual(words("new AnalyserNode(); ctx.createAnalyser()"), [])
        self.assertEqual(words("except asyncio.CancelledError: pass"), [])
        self.assertEqual(words("if Task.isCancelled { return }; case NSURLErrorCancelled:"), [])

    def test_metric_compounds(self):
        self.assertEqual(words("millimetres centimetre kilometres"), [("millimetres", "millimeters"), ("centimetre", "centimeter"), ("kilometres", "kilometers")])


class British(unittest.TestCase):
    def test_flags_american_spellings_with_british_fixes(self):
        self.assertEqual(
            words("color center canceled analyzed normalize", "british"),
            [("color", "colour"), ("center", "centre"), ("canceled", "cancelled"), ("analyzed", "analysed"),
             ("normalize", "normalise")],
        )

    def test_leaves_british_text_alone(self):
        self.assertEqual(words("colour centre cancelled analysed normalise", "british"), [])

    def test_does_not_flag_words_that_are_correct_british_too(self):
        # A computer program, a gas meter, to check, to license, a practice, a judgment (legal), analog circuits.
        self.assertEqual(words("program meter check license practice judgment analog story tire gray", "british"), [])

    def test_oxford_spelling_keeps_ize_but_still_wants_our_re_and_double_l(self):
        self.assertEqual(words("organize normalize", "british-oxford"), [])
        self.assertEqual(
            words("color center canceled analyzed", "british-oxford"),
            [("color", "colour"), ("center", "centre"), ("canceled", "cancelled"), ("analyzed", "analysed")],
        )
        self.assertEqual(words("organise", "british-oxford"), [("organise", "organize")])


class Exceptions(unittest.TestCase):
    def test_line_marker(self):
        self.assertEqual(words('label = "Colour"  # spelling: ok'), [])

    def test_allowed_words_match_inside_identifiers(self):
        self.assertEqual(words("led.setColour(1) centre", allowed={"colour"}), [("centre", "center")])


class Repo(unittest.TestCase):
    def test_checks_tracked_text_files(self):
        root = repo({"README.md": "Pick a colour.\n", "src/app.go": "func centreOf() {}\n", "logo.png": "colour"})
        self.assertEqual(check_repo(root), ["README.md:1: colour -> color", "src/app.go:1: centre -> center"])

    def test_config_file_sets_dialect_allows_words_and_skips_paths(self):
        root = repo({
            ".spelling-dialect": "dialect: british\n# a stored value\ncanceled\npath: vendor/\n",
            "a.md": "The color, canceled.\n",
            "vendor/x.md": "center\n",
        })
        self.assertEqual(check_repo(root), ["a.md:1: color -> colour"])

    def test_dialect_argument_overrides_config(self):
        root = repo({".spelling-dialect": "dialect: british\n", "a.md": "colour\n"})
        self.assertEqual(check_repo(root, dialect="american"), ["a.md:1: colour -> color"])

    def test_github_actions_own_cancelled_value_is_allowed_in_workflows(self):
        root = repo({
            ".github/workflows/ci.yml": "if: ${{ cancelled() || needs.a.result == 'cancelled' }}\n",
            "docs/notes.md": "The run was cancelled.\n",
        })
        self.assertEqual(check_repo(root), ["docs/notes.md:1: cancelled -> canceled"])

    def test_file_opt_out(self):
        root = repo({"words.py": "# spelling: skip-file\ncolour\n", "app.py": "colour\n"})
        self.assertEqual(check_repo(root), ["app.py:1: colour -> color"])

    def test_checks_only_given_files_for_pre_commit(self):
        root = repo({"a.md": "colour\n", "b.md": "centre\n"})
        self.assertEqual(check_repo(root, files=["b.md"]), ["b.md:1: centre -> center"])

    def test_reads_the_older_american_spelling_allow_file(self):
        root = repo({".american-spelling-allow": "colour\n", "a.md": "colour centre\n"})
        self.assertEqual(check_repo(root), ["a.md:1: centre -> center"])


class Scope(unittest.TestCase):
    def test_british_checks_docs_only_by_default_because_code_apis_are_american(self):
        root = repo({".spelling-dialect": "dialect: british\n", "style.css": "a { color: gray; text-align: center }\n",
                     "README.md": "Pick a color.\n"})
        self.assertEqual(check_repo(root), ["README.md:1: color -> colour"])

    def test_scope_all_checks_code_too(self):
        root = repo({".spelling-dialect": "dialect: british\nscope: all\n", "notes.txt": "colour\n", "app.py": "# the color\n"})
        self.assertEqual(check_repo(root), ["app.py:1: color -> colour"])


class Cli(unittest.TestCase):
    def test_exit_codes_and_output(self):
        root = repo({"a.md": "colour\n"})
        script = Path(__file__).resolve().parent.parent / "spelling_dialect.py"
        bad = subprocess.run([sys.executable, str(script), str(root)], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn("a.md:1: colour -> color", bad.stdout)
        good = subprocess.run([sys.executable, str(script), "--dialect", "british", str(root)], capture_output=True, text=True)
        self.assertEqual((good.returncode, good.stdout.strip()), (0, "Spelling (british): OK"))


if __name__ == "__main__":
    unittest.main()
