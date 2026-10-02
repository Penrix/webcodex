import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json_boundary as jb  # noqa: E402


class JsonBoundaryTests(unittest.TestCase):
    def test_observed_turndown_corruption_recovers(self):
        observed = '{"kind":"call","tool":"read\\_files","params":{"paths":\\["acceptance.py"\\]},"text":null}'
        self.assertEqual(
            jb.parse_json_object_from_markdown(observed),
            {
                "kind": "call",
                "tool": "read_files",
                "params": {"paths": ["acceptance.py"]},
                "text": None,
            },
        )

    def test_valid_json_backslashes_remain_literal(self):
        raw = '{"kind":"final","tool":null,"params":null,"text":"C:\\\\_keep\\\\[x]"}'
        value = jb.parse_json_object_from_markdown(raw)
        self.assertEqual(value["text"], r"C:\\_keep\\[x]")

    def test_unrelated_invalid_json_escape_is_not_repaired(self):
        raw = '{"kind":"final","tool":null,"params":null,"text":"bad\\q"}'
        with self.assertRaises(ValueError):
            jb.parse_json_object_from_markdown(raw)


if __name__ == "__main__":
    unittest.main()
