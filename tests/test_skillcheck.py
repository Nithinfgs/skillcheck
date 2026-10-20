import json
import tempfile
import unittest
from pathlib import Path

from skillcheck.cli import main
from skillcheck.core import lint_tree, parse_frontmatter

GOOD = """---
name: pdf-tools
description: Extract and merge PDF files. Use when the user mentions PDFs, forms or page splitting.
---
# PDF tools
See [guide](references/guide.md) and run `scripts/run.py`.
"""


def make(root: Path, name: str, text: str, files=()):
    d = root / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(text)
    for f in files:
        (d / f).parent.mkdir(parents=True, exist_ok=True)
        (d / f).write_text("x")
    return d


def rules(findings):
    return {f.rule for f in findings}


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_skill(self):
        make(self.root, "pdf-tools", GOOD, ["references/guide.md", "scripts/run.py"])
        self.assertEqual(lint_tree(self.root), [])

    def test_missing_frontmatter(self):
        make(self.root, "a", "# no frontmatter\n")
        self.assertIn("frontmatter", rules(lint_tree(self.root)))

    def test_bad_name_and_dir_mismatch(self):
        make(self.root, "folder", GOOD.replace("pdf-tools", "PDF_Tools"), ["references/guide.md", "scripts/run.py"])
        r = rules(lint_tree(self.root))
        self.assertIn("name-format", r)
        self.assertIn("name-dir", r)

    def test_missing_reference(self):
        make(self.root, "pdf-tools", GOOD)
        r = [f for f in lint_tree(self.root) if f.rule == "ref-missing"]
        self.assertEqual(len(r), 2)

    def test_fenced_paths_ignored(self):
        text = GOOD.split("# PDF")[0] + "# x\n```\n`scripts/nope.py`\n```\nbody\n"
        make(self.root, "pdf-tools", text)
        self.assertNotIn("ref-missing", rules(lint_tree(self.root)))

    def test_description_without_trigger(self):
        text = "---\nname: x-y\ndescription: A very helpful skill that does many wonderful things.\n---\nBody\n"
        make(self.root, "x-y", text)
        self.assertIn("desc-trigger", rules(lint_tree(self.root)))

    def test_folded_description(self):
        fm, _, err = parse_frontmatter("---\nname: a\ndescription: >\n  line one\n  line two\n---\nb")
        self.assertIsNone(err)
        self.assertEqual(fm["description"], "line one line two")

    def test_duplicate_names_and_overlap(self):
        d = "Convert spreadsheet files into clean csv output. Use when the user wants csv conversion."
        t = lambda n: f"---\nname: {n}\ndescription: {d}\n---\nBody\n"
        make(self.root, "one", t("same"))
        make(self.root, "two", t("same"))
        make(self.root, "three", t("other"))
        r = rules(lint_tree(self.root))
        self.assertIn("name-dup", r)
        self.assertIn("desc-overlap", r)

    def test_orphan_note(self):
        make(self.root, "pdf-tools", GOOD, ["references/guide.md", "scripts/run.py", "assets/unused.png"])
        self.assertIn("ref-orphan", rules(lint_tree(self.root)))

    def test_cli_exit_codes_and_json(self):
        make(self.root, "pdf-tools", GOOD)
        self.assertEqual(main([str(self.root), "--format", "json"]), 1)
        self.assertEqual(main([str(self.root), "--ignore", "ref-missing"]), 0)
        self.assertEqual(main([str(self.root), "--fail-on", "never"]), 0)
        self.assertEqual(main([str(self.root / "missing")]), 2)

    def test_empty_tree(self):
        self.assertIn("no-skills", rules(lint_tree(self.root)))


if __name__ == "__main__":
    unittest.main()
