# -*- coding: utf-8 -*-
"""Tests for the self-implemented YAML subset parser."""

# pylint: disable=missing-docstring
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from skillaudit.yamlmini import (  # noqa: E402
    YamlMiniError, extract_front_matter, loads,
)


class ScalarTests(unittest.TestCase):
    def test_plain_mapping(self):
        self.assertEqual(loads("name: demo"), {"name": "demo"})

    def test_type_coercion(self):
        parsed = loads("a: 1\nb: 2.5\nc: true\nd: false\ne: yes\nf: off\ng: null")
        self.assertEqual(parsed, {
            "a": 1, "b": 2.5, "c": True, "d": False,
            "e": True, "f": False, "g": None,
        })

    def test_quoted_scalars_preserve_content(self):
        parsed = loads("a: '0012'\nb: \"hello: world\"\nc: 'it''s'")
        self.assertEqual(parsed["a"], "0012")
        self.assertEqual(parsed["b"], "hello: world")
        self.assertEqual(parsed["c"], "it's")

    def test_empty_value_is_none(self):
        parsed = loads("a:")
        self.assertIsNone(parsed["a"])

    def test_comment_is_stripped(self):
        parsed = loads("a: value   # trailing note\nb: 'hash # inside'")
        self.assertEqual(parsed["a"], "value")
        self.assertEqual(parsed["b"], "hash # inside")

    def test_comment_only_line_ignored(self):
        parsed = loads("# leading note\na: 1\n\n# another\nb: 2")
        self.assertEqual(parsed, {"a": 1, "b": 2})


class BlockScalarTests(unittest.TestCase):
    def test_folded_block(self):
        parsed = loads("desc: >-\n  first line\n  second line\n")
        self.assertEqual(parsed["desc"], "first line second line")

    def test_literal_block_keeps_newlines(self):
        parsed = loads("body: |\n  line one\n  line two\n")
        self.assertEqual(parsed["body"], "line one\nline two\n")

    def test_literal_strip_chomp(self):
        parsed = loads("body: |-\n  line one\n  line two\n")
        self.assertEqual(parsed["body"], "line one\nline two")

    def test_folded_blank_line_becomes_paragraph_break(self):
        parsed = loads("desc: >-\n  para one\n\n  para two\n")
        self.assertEqual(parsed["desc"], "para one\npara two")

    # --- regression -----------------------------------------------------
    def test_following_keys_survive_folded_scalar(self):
        """A folded block must not swallow subsequent scalar keys."""
        parsed = loads("description: >-\n  long text\n  continues\n"
                       "version: 1.0.0\nlicense: MIT\n")
        self.assertEqual(parsed["version"], "1.0.0")
        self.assertEqual(parsed["license"], "MIT")

    def test_following_keys_survive_literal_scalar(self):
        parsed = loads("body: |\n  raw text\n  more raw\nname: x\nlisted: false\n")
        self.assertEqual(parsed["name"], "x")
        self.assertEqual(parsed["listed"], False)

    def test_block_scalar_then_nested_mapping(self):
        parsed = loads("desc: >-\n  folded text\nmetadata:\n  author: me\n")
        self.assertEqual(parsed["desc"], "folded text")
        self.assertEqual(parsed["metadata"], {"author": "me"})


class SequenceTests(unittest.TestCase):
    def test_simple_sequence(self):
        parsed = loads("tools:\n  - Read\n  - Grep\n  - Bash")
        self.assertEqual(parsed["tools"], ["Read", "Grep", "Bash"])

    def test_sequence_of_numbers_and_booleans(self):
        parsed = loads("values:\n  - 1\n  - true\n  - 3.5")
        self.assertEqual(parsed["values"], [1, True, 3.5])

    def test_sequence_of_mappings(self):
        parsed = loads("items:\n  - name: first\n    score: 10\n  - name: second\n"
                       "    score: 20")
        self.assertEqual(parsed["items"], [
            {"name": "first", "score": 10},
            {"name": "second", "score": 20},
        ])

    def test_sequence_surrounded_by_scalars(self):
        parsed = loads("a: 1\nseq:\n  - x\n  - y\nb: 2")
        self.assertEqual(parsed, {"a": 1, "seq": ["x", "y"], "b": 2})

    def test_block_scalar_inside_sequence(self):
        parsed = loads("entries:\n  - >-\n    folded entry\n  - plain")
        self.assertEqual(parsed["entries"], ["folded entry", "plain"])


class NestingTests(unittest.TestCase):
    def test_nested_mapping(self):
        parsed = loads("outer:\n  inner:\n    leaf: 42\ntop: value")
        self.assertEqual(parsed, {
            "outer": {"inner": {"leaf": 42}},
            "top": "value",
        })

    def test_dotted_key_kept_as_is(self):
        parsed = loads("allowed-tools: Bash Read")
        self.assertEqual(parsed["allowed-tools"], "Bash Read")

    def test_empty_document(self):
        self.assertIsNone(loads(""))
        self.assertIsNone(loads("# only a comment\n"))

    def test_bad_indentation_raises(self):
        with self.assertRaises(YamlMiniError):
            loads("a: 1\n  b: 2")


class FrontMatterTests(unittest.TestCase):
    def test_extract_with_body(self):
        text = "---\nname: demo\n---\n\n# Title\n\ncontent\n"
        mapping, body, _ = extract_front_matter(text)
        self.assertEqual(mapping, {"name": "demo"})
        self.assertIn("# Title", body)

    def test_extract_without_front_matter(self):
        text = "# Just markdown\n"
        mapping, body, _ = extract_front_matter(text)
        self.assertIsNone(mapping)
        self.assertEqual(body, text)

    def test_extract_empty_front_matter(self):
        mapping, _, _ = extract_front_matter("---\n---\nbody\n")
        self.assertEqual(mapping, {})

    def test_extract_none_input(self):
        mapping, body, _ = extract_front_matter(None)
        self.assertIsNone(mapping)
        self.assertEqual(body, "")

    def test_real_world_manifest(self):
        text = (
            "---\n"
            "name: csv-insight\n"
            "description: >-\n"
            "  Profile CSV files. Use when the user asks to inspect tabular data.\n"
            "version: 1.0.0\n"
            "license: MIT\n"
            "metadata:\n"
            "  author: qa\n"
            "allowed-tools:\n"
            "  - Read\n"
            "  - Bash\n"
            "---\n\n# Intro\n"
        )
        mapping, body, _ = extract_front_matter(text)
        self.assertEqual(mapping["name"], "csv-insight")
        self.assertEqual(mapping["version"], "1.0.0")
        self.assertEqual(mapping["license"], "MIT")
        self.assertEqual(mapping["metadata"], {"author": "qa"})
        self.assertEqual(mapping["allowed-tools"], ["Read", "Bash"])
        self.assertIn("Use when", mapping["description"])
        self.assertIn("# Intro", body)


if __name__ == "__main__":
    unittest.main()
