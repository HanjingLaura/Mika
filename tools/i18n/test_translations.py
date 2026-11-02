"""Behavioral tests for the standalone translation CLI (no Android SDK)."""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("translations.py")


class TranslationCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.res = self.root / "res"

    def write(self, folder, body, filename="strings.xml"):
        path = self.res / folder / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<resources>{body}</resources>", encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--res-dir", str(self.res), *args],
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_missing_and_extra_keys_are_reported_together(self):
        self.write("values", '<string name="save">Save</string><plurals name="tasks"><item quantity="other">Tasks</item></plurals>')
        self.write("values-ja", '<string name="old">Old</string>')
        result = self.run_cli("check")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("values-ja: missing string/save", result.stdout)
        self.assertIn("values-ja: missing plurals/tasks", result.stdout)
        self.assertIn("values-ja: extra string/old", result.stdout)

    def test_keys_can_move_between_files_and_fixed_strings_are_not_required(self):
        self.write("values", '<string name="app_name" translatable="false">Mika</string><string name="save">Save</string>')
        self.write("values-ja", '<string name="save">保存</string>', "strings_actions.xml")
        self.write("values-night", '<string name="night_only">Night</string>')
        self.assertEqual(self.run_cli("check").returncode, 0)

    def test_plural_quantities_can_differ_between_languages(self):
        self.write("values", '<plurals name="tasks"><item quantity="one">One task</item><item quantity="other">Tasks</item></plurals>')
        self.write("values-ru", '<plurals name="tasks"><item quantity="one">Одна</item><item quantity="few">Несколько</item><item quantity="many">Много</item><item quantity="other">Задачи</item></plurals>')
        self.assertEqual(self.run_cli("check").returncode, 0)

    def test_duplicate_keys_across_files_are_not_silently_overwritten(self):
        self.write("values", '<string name="save">Save</string>')
        self.write("values", '<string name="save">Again</string>', "strings_more.xml")
        result = self.run_cli("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate string/save", result.stderr)

    def test_malformed_xml_names_the_file(self):
        self.write("values", '<string name="save">')
        result = self.run_cli("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("strings.xml", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_wrong_resource_type_is_a_missing_and_extra_key(self):
        self.write("values", '<string name="save">Save</string>')
        self.write("values-es", '<string-array name="save"><item>Guardar</item></string-array>')
        result = self.run_cli("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing string/save", result.stdout)
        self.assertIn("extra string-array/save", result.stdout)

    def test_empty_resource_root_is_an_error(self):
        self.res.mkdir()
        result = self.run_cli("check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("values", result.stderr)

    def test_export_has_reference_columns_context_and_lossless_cells(self):
        self.write("values", '''<!-- Shown before saving. -->
            <string name="save">Save, &quot;now&quot;\n<b>please</b>\\n%1$s</string>
            <string name="fixed" translatable="false">Mika</string>
            <plurals name="tasks"><item quantity="one">One</item><item quantity="other">Many</item></plurals>
            <string-array name="choices"><item>Yes</item><item>No</item></string-array>''')
        self.write("values-zh", '<string name="save">保存</string>')
        self.write("values-b+zh+Hant", '<string name="save">儲存</string>')
        self.write("values-ru", '<plurals name="tasks"><item quantity="few">Несколько</item><item quantity="other">Задачи</item></plurals>')
        output = self.root / "reference.csv"
        result = self.run_cli("export", "--output", str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
        with output.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames[:8], ["key", "type", "item", "source", "context", "values", "values-zh", "values-b+zh+Hant"])
            rows = list(reader)
        save = next(row for row in rows if row["key"] == "save")
        self.assertEqual(save["values"], 'Save, "now"\n<b>please</b>\\n%1$s')
        self.assertEqual(save["context"], "Shown before saving.")
        self.assertEqual(save["source"], "values/strings.xml")
        self.assertEqual(save["values-zh"], "保存")
        self.assertEqual(save["values-b+zh+Hant"], "儲存")
        self.assertNotIn("fixed", [row["key"] for row in rows])
        few = next(row for row in rows if row["key"] == "tasks" and row["item"] == "few")
        self.assertEqual(few["values"], "")
        self.assertEqual(few["values-ru"], "Несколько")
        choices = [row for row in rows if row["key"] == "choices"]
        self.assertEqual([(row["item"], row["values"]) for row in choices], [("0", "Yes"), ("1", "No")])
        first = output.read_bytes()
        self.assertEqual(self.run_cli("export", "--output", str(output)).returncode, 0)
        self.assertEqual(output.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
