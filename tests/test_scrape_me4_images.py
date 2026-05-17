"""Tests for scripts/scrape_me4_images.py."""
import pathlib
import re
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


class TestFetchAllImageUrls(unittest.TestCase):
    def test_paginates_until_empty_page(self):
        responses = [
            '<li class="card"><img data-original="https://asia.pokemon-card.com/sg/card-img/default00025192.png"></li>',
            '<li class="card"><img data-original="https://asia.pokemon-card.com/sg/card-img/default00025193.png"></li>',
            "<html><body>no cards</body></html>",
        ]
        calls = []

        def fake_fetch(url, timeout=15):
            calls.append(url)
            return responses.pop(0)

        with patch("scrape_me4_images._fetch", side_effect=fake_fetch):
            urls = scrape_me4_images.fetch_all_image_urls(sleep_seconds=0)

        self.assertEqual(urls, [
            "https://asia.pokemon-card.com/sg/card-img/default00025192.png",
            "https://asia.pokemon-card.com/sg/card-img/default00025193.png",
        ])
        self.assertEqual(len(calls), 3)
        self.assertIn("pageNo=1", calls[0])
        self.assertIn("pageNo=2", calls[1])
        self.assertIn("pageNo=3", calls[2])


class TestResolveNames(unittest.TestCase):
    def test_resolves_name_for_each_image_url(self):
        urls = [
            "https://asia.pokemon-card.com/sg/card-img/default00025192.png",
            "https://asia.pokemon-card.com/sg/card-img/default00025193.png",
        ]
        responses_by_id = {
            25192: "<title>Weedle | Trainers Website</title>",
            25193: "<title>Kakuna | Trainers Website</title>",
        }

        def fake_fetch(url, timeout=15):
            m = re.search(r"/detail/(\d+)/", url)
            return responses_by_id[int(m.group(1))]

        with patch("scrape_me4_images._fetch", side_effect=fake_fetch):
            ordered = scrape_me4_images.resolve_names(urls, sleep_seconds=0)

        self.assertEqual(ordered, [
            {"name": "Weedle", "image": urls[0]},
            {"name": "Kakuna", "image": urls[1]},
        ])

    def test_raises_when_a_detail_page_has_no_title(self):
        urls = ["https://asia.pokemon-card.com/sg/card-img/default00025192.png"]
        with patch("scrape_me4_images._fetch", return_value="<html></html>"):
            with self.assertRaises(RuntimeError):
                scrape_me4_images.resolve_names(urls, sleep_seconds=0)


class TestBuildSidecar(unittest.TestCase):
    def test_produces_byname_and_ordered(self):
        ordered_input = [
            {"name": "Weedle", "image": "https://example.com/a.png"},
            {"name": "Kakuna", "image": "https://example.com/b.png"},
        ]
        sidecar = scrape_me4_images.build_sidecar(ordered_input, scraped_at="2026-05-17")
        self.assertEqual(sidecar["set"], "ME4")
        self.assertEqual(sidecar["source"], "asia.pokemon-card.com")
        self.assertEqual(sidecar["scrapedAt"], "2026-05-17")
        self.assertEqual(sidecar["byName"]["Weedle"], "https://example.com/a.png")
        self.assertEqual(sidecar["byName"]["Kakuna"], "https://example.com/b.png")
        self.assertEqual(sidecar["ordered"], ordered_input)

    def test_duplicate_names_keep_first_in_byname_but_all_in_ordered(self):
        ordered_input = [
            {"name": "Deoxys", "image": "https://example.com/d1.png"},
            {"name": "Deoxys", "image": "https://example.com/d2.png"},
            {"name": "Deoxys", "image": "https://example.com/d3.png"},
        ]
        sidecar = scrape_me4_images.build_sidecar(ordered_input, scraped_at="2026-05-17")
        self.assertEqual(sidecar["byName"]["Deoxys"], "https://example.com/d1.png")
        self.assertEqual(len(sidecar["ordered"]), 3)
        self.assertEqual([e["image"] for e in sidecar["ordered"]],
                         ["https://example.com/d1.png", "https://example.com/d2.png", "https://example.com/d3.png"])


class TestResolveScrapedAt(unittest.TestCase):
    def test_uses_today_when_no_prior_file(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "missing.json"
            result = scrape_me4_images._resolve_scraped_at(
                path, new_byname={}, new_ordered=[], today_iso="2026-05-17"
            )
            self.assertEqual(result, "2026-05-17")

    def test_preserves_prior_when_content_unchanged(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "sidecar.json"
            path.write_text(json.dumps({
                "scrapedAt": "2026-04-01",
                "byName": {"Weedle": "x"},
                "ordered": [{"name": "Weedle", "image": "x"}],
            }))
            result = scrape_me4_images._resolve_scraped_at(
                path,
                new_byname={"Weedle": "x"},
                new_ordered=[{"name": "Weedle", "image": "x"}],
                today_iso="2026-05-17",
            )
            self.assertEqual(result, "2026-04-01")

    def test_uses_today_when_content_changed(self):
        import tempfile, json
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "sidecar.json"
            path.write_text(json.dumps({
                "scrapedAt": "2026-04-01",
                "byName": {"Weedle": "old.png"},
                "ordered": [{"name": "Weedle", "image": "old.png"}],
            }))
            result = scrape_me4_images._resolve_scraped_at(
                path,
                new_byname={"Weedle": "new.png"},
                new_ordered=[{"name": "Weedle", "image": "new.png"}],
                today_iso="2026-05-17",
            )
            self.assertEqual(result, "2026-05-17")


class TestSanityCheck(unittest.TestCase):
    def test_passes_when_first_name_matches_expected(self):
        ordered = [{"name": "Weedle", "image": "x"}, {"name": "Kakuna", "image": "y"}]
        scrape_me4_images.sanity_check(ordered, me4_names={"Weedle", "Kakuna"})

    def test_raises_when_first_name_is_unexpected(self):
        ordered = [{"name": "Pikachu", "image": "x"}]
        with self.assertRaises(RuntimeError):
            scrape_me4_images.sanity_check(ordered, me4_names={"Weedle"})

    def test_raises_when_too_few_me4_names_overlap(self):
        ordered = [{"name": "Weedle", "image": "x"}] + [
            {"name": f"Unknown{i}", "image": "y"} for i in range(120)
        ]
        me4_names = {"Weedle"} | {f"Card{i}" for i in range(82)}
        with self.assertRaises(RuntimeError):
            scrape_me4_images.sanity_check(ordered, me4_names=me4_names)


if __name__ == "__main__":
    unittest.main()
