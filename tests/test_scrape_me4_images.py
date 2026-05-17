"""Tests for scripts/scrape_me4_images.py."""
import pathlib
import sys
import unittest
from unittest.mock import patch, MagicMock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import scrape_me4_images  # noqa: E402


class TestParseListingPage(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "tests" / "fixtures" / "me04_list_page1.html").read_text()

    def test_extracts_20_image_urls_in_order(self):
        urls = scrape_me4_images.parse_listing_page(self.html)
        self.assertEqual(len(urls), 20)
        self.assertEqual(urls[0], "https://asia.pokemon-card.com/sg/card-img/default00025192.png")
        self.assertEqual(urls[-1], "https://asia.pokemon-card.com/sg/card-img/default00025211.png")

    def test_returns_empty_list_when_no_cards(self):
        self.assertEqual(scrape_me4_images.parse_listing_page("<html></html>"), [])


class TestExtractDetailName(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "tests" / "fixtures" / "me04_detail_25192.html").read_text()

    def test_extracts_weedle_from_real_detail_page(self):
        self.assertEqual(scrape_me4_images.extract_detail_name(self.html), "Weedle")

    def test_handles_card_with_apostrophe(self):
        html = "<title>Roxie's Performance | Trainers Website</title>"
        self.assertEqual(scrape_me4_images.extract_detail_name(html), "Roxie's Performance")

    def test_handles_card_with_curly_braces(self):
        html = "<title>Bubbly {W} Energy | Trainers Website</title>"
        self.assertEqual(scrape_me4_images.extract_detail_name(html), "Bubbly {W} Energy")

    def test_returns_none_when_no_title(self):
        self.assertIsNone(scrape_me4_images.extract_detail_name("<html></html>"))

    def test_extracts_detail_id_from_image_url(self):
        self.assertEqual(
            scrape_me4_images._detail_id_from_image_url(
                "https://asia.pokemon-card.com/sg/card-img/default00025192.png"
            ),
            25192,
        )


if __name__ == "__main__":
    unittest.main()
