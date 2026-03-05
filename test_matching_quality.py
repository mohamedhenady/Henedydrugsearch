import unittest

import matcher_v2


class TestMatchingQuality(unittest.TestCase):
    def test_clean_for_match_normalizes_eastern_arabic_digits(self):
        cleaned = matcher_v2.clean_for_match("Concor ٥mg")
        self.assertEqual(cleaned, "concor 5")

    def test_strength_sensitive_match_for_concor(self):
        results = matcher_v2.search_live("Concor 5mg", limit=5)
        self.assertTrue(results, "Expected at least one search result for Concor 5mg")

        top_name = str(results[0].get("name_en", "")).lower()
        self.assertIn("concor", top_name)
        self.assertRegex(top_name, r"5\s*mg|\b5\b")

    def test_ratio_query_prefers_ratio_candidates(self):
        results = matcher_v2.search_live("Co targe 160/12.5", limit=5)
        self.assertTrue(results, "Expected at least one search result for Co targe 160/12.5")

        top_name = str(results[0].get("name_en", "")).lower().replace(" ", "")
        self.assertIn("160/12.5", top_name)

    def test_scores_are_sorted_descending(self):
        results = matcher_v2.search_live("paracetamol 500mg", limit=10)
        self.assertTrue(results, "Expected at least one search result for paracetamol 500mg")

        scores = [float(row.get("_score", 0)) for row in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
