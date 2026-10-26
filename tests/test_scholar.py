import copy
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import refresh_scholar as r
import verify_scholar_publish as v

NOW = dt.datetime(2026, 11, 2, 7, 23, tzinfo=dt.timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def fixture():
    # Synthetic test values only; never publish this fixture.
    return {
        "search_metadata": {"status": "Success"},
        "search_parameters": {"engine": "google_scholar_author", "author_id": r.AUTHOR_ID},
        "author": {"name": "David Slomp"},
        "cited_by": {"table": [
            {"citations": {"all": 1500, "since_2021": 900}},
            {"h_index": {"all": 20, "since_2021": 15}},
            {"i10_index": {"all": 32, "since_2021": 21}},
        ]},
    }


class ParserTests(unittest.TestCase):
    def test_valid_all_and_recent_are_not_confused(self):
        result = r.normalize_payload(fixture(), NOW)
        self.assertEqual(result["metrics"]["citations"], {"all": 1500, "recent": 900})
        self.assertEqual(result["metrics"]["h_index"], {"all": 20, "recent": 15})
        self.assertEqual(result["metrics"]["i10_index"], {"all": 32, "recent": 21})
        self.assertEqual(result["checked_at"], "2026-11-02T07:23:00Z")
        rendered = r.render_section(result)
        for text in ["1,500", "About 60%", "since 2021", "2 November 2026", 'data-scholar-checked-at="2026-11-02T07:23:00Z"']:
            self.assertIn(text, rendered)

    def test_recent_year_comes_from_response(self):
        payload = fixture()
        for row in payload["cited_by"]["table"]:
            metric = next(iter(row.values()))
            metric["since_2022"] = metric.pop("since_2021")
        result = r.normalize_payload(payload, NOW)
        self.assertIn("since 2022", r.render_section(result))
        self.assertNotIn("since 2021", r.render_section(result))

    def test_no_i10_is_invented(self):
        payload = fixture()
        payload["cited_by"]["table"].pop()
        self.assertNotIn("i10_index", r.normalize_payload(payload, NOW)["metrics"])

    def test_impossible_h_index_rejected(self):
        payload = fixture(); payload["cited_by"]["table"][1]["h_index"]["all"] = 50
        with self.assertRaises(r.RefreshError): r.normalize_payload(payload, NOW)

    def test_saved_snapshot_identity_is_validated(self):
        snapshot = json.loads((ROOT / "data/scholar-metrics.json").read_text())
        r.validate_snapshot(snapshot)
        snapshot["author_id"] = "wrong"
        with self.assertRaises(r.RefreshError): r.validate_snapshot(snapshot)

    def test_validation_diagnostics_only_contain_fixed_categories(self):
        payload = fixture(); payload["author"]["name"] = "sensitive-untrusted-response-text"
        with self.assertRaises(r.RefreshError) as caught:
            r.normalize_payload(payload, NOW)
        self.assertIn("author name", str(caught.exception))
        self.assertNotIn("sensitive-untrusted", str(caught.exception))

    def test_documented_name_variant_is_diagnostic_only(self):
        payload = fixture(); payload["author"]["name"] = "David H. Slomp"
        with self.assertRaises(r.RefreshError) as caught:
            r.normalize_payload(payload, NOW)
        self.assertIn("documented middle-initial variant", str(caught.exception))

    def test_name_normalization(self):
        payload = fixture(); payload["author"]["name"] = " DAVID   SLOMP "
        self.assertEqual(r.normalize_payload(payload, NOW)["author_name"], "David Slomp")

    def test_historical_baseline_never_has_check_date(self):
        baseline = {"checked_at": None}
        page = r.render_section(baseline)
        for text in ["1,200+", "Nearly 70%", "September 2026 snapshot", "not yet verified"]:
            self.assertIn(text, page)
        self.assertNotIn("Last successful check", page)
        self.assertNotIn("i10", page)

    def test_invalid_payloads_rejected(self):
        variants = [None, [], {}, {"error": "sensitive-provider-text"}]
        edits = [
            lambda p: p["search_metadata"].update(status="Processing"),
            lambda p: p["search_parameters"].update(author_id="wrong"),
            lambda p: p["search_parameters"].update(engine="google_scholar"),
            lambda p: p["author"].update(name="Someone Else"),
            lambda p: p.pop("cited_by"),
            lambda p: p["cited_by"]["table"].pop(1),
            lambda p: p["cited_by"]["table"][0]["citations"].pop("all"),
            lambda p: p["cited_by"]["table"][0]["citations"].pop("since_2021"),
            lambda p: p["cited_by"]["table"][0]["citations"].update(since_2022=800),
            lambda p: p["cited_by"]["table"][0]["citations"].update(since_2021=2000),
            lambda p: p["cited_by"]["table"].append(copy.deepcopy(p["cited_by"]["table"][0])),
        ]
        for edit in edits:
            payload = fixture(); edit(payload); variants.append(payload)
        for value in [-1, True, "1500", 1.5, None, 1_000_000_001]:
            payload = fixture(); payload["cited_by"]["table"][0]["citations"]["all"] = value
            variants.append(payload)
        for payload in variants:
            with self.subTest(payload=payload), self.assertRaises(r.RefreshError):
                r.normalize_payload(payload, NOW)

    def test_inconsistent_year_rejected(self):
        payload = fixture()
        payload["cited_by"]["table"][1]["h_index"] = {"all": 20, "since_2022": 15}
        with self.assertRaises(r.RefreshError): r.normalize_payload(payload, NOW)

    def test_zero_total_does_not_invent_percentage(self):
        payload = fixture()
        for row in payload["cited_by"]["table"]:
            metric = next(iter(row.values())); metric.update(all=0, since_2021=0)
        self.assertIn("<dd>—</dd>", r.render_section(r.normalize_payload(payload, NOW)))


class FailureSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root / "data").mkdir()
        self.paths = [self.root / "data/scholar-metrics.json", self.root / "index.html"]
        self.paths[0].write_text('{"checked_at": null}\n')
        self.paths[1].write_text("BEFORE\n" + r.render_section({"checked_at": None}) + "\nAFTER")
        self.originals = [p.read_bytes() for p in self.paths]

    def unchanged(self):
        self.assertEqual([p.read_bytes() for p in self.paths], self.originals)

    def test_missing_key_does_not_fetch_or_mutate(self):
        with patch.object(r.urllib.request, "build_opener") as opener:
            with self.assertRaises(r.RefreshError): r.refresh(self.root, api_key="", now=NOW)
            opener.assert_not_called()
        self.unchanged()

    def test_all_validation_failures_do_not_mutate(self):
        for payload in [{"error": "invalid key"}, {}, {**fixture(), "author": {"name": "Wrong"}}]:
            with patch.object(r, "fetch_payload", return_value=payload), self.assertRaises(r.RefreshError):
                r.refresh(self.root, api_key="fake-test-key", now=NOW)
            self.unchanged()

    def test_network_and_json_errors_do_not_leak_key_or_mutate(self):
        secret = "fake-test-secret-never-real"
        for error in [TimeoutError(secret), urllib.error.HTTPError("https://serpapi.com/?api_key=" + secret, 429, secret, {}, None)]:
            with patch.object(r.urllib.request, "build_opener") as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(r.RefreshError) as caught:
                    r.refresh(self.root, api_key=secret, now=NOW)
                self.assertNotIn(secret, str(caught.exception))
            self.unchanged()
        with patch.object(r.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'{bad json'
            with self.assertRaises(r.RefreshError): r.refresh(self.root, api_key=secret, now=NOW)
        self.unchanged()

    def test_oversized_response_is_rejected(self):
        with patch.object(r.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b"x" * (r.MAX_RESPONSE_BYTES + 1)
            with self.assertRaises(r.RefreshError): r.refresh(self.root, api_key="fake", now=NOW)
        self.unchanged()

    def test_redirect_is_not_followed(self):
        with self.assertRaises(r.RefreshError): r.NoRedirect().redirect_request(None, None, 302, None, None, "https://other.test")

    def test_request_settings_and_no_response_storage(self):
        with patch.object(r.urllib.request, "build_opener") as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = json.dumps(fixture()).encode()
            r.refresh(self.root, api_key="fake-test-key", now=NOW)
            request = opener.return_value.open.call_args.args[0]
            params = r.urllib.parse.parse_qs(r.urllib.parse.urlsplit(request.full_url).query)
            self.assertEqual(params["hl"], ["en"])
            self.assertEqual(params["no_cache"], ["true"])
            self.assertEqual(params["author_id"], [r.AUTHOR_ID])
            self.assertEqual(opener.return_value.open.call_count, 1)
        self.assertNotIn("fake-test-key", self.paths[0].read_text() + self.paths[1].read_text())
        self.assertNotIn("search_metadata", self.paths[0].read_text())
        self.assertTrue(self.paths[1].read_text().startswith("BEFORE\n"))
        self.assertTrue(self.paths[1].read_text().endswith("\nAFTER"))

    def test_missing_duplicate_and_reversed_markers_rejected(self):
        for text in ["no markers", r.START + r.START + r.END, r.END + r.START]:
            with self.assertRaises(r.RefreshError): r.updated_index(text, {"checked_at": None})

    def test_local_write_failure_rolls_back_both_files(self):
        real_replace = r.os.replace
        count = 0
        def fail_second(src, dst):
            nonlocal count
            count += 1
            if count == 2: raise OSError("disk error")
            return real_replace(src, dst)
        with patch.object(r.os, "replace", side_effect=fail_second), self.assertRaises(r.RefreshError):
            r.write_outputs(self.root, r.normalize_payload(fixture(), NOW))
        self.unchanged()
        self.assertEqual(len(list(self.root.glob("data/*"))), 1)


class PublicationTests(unittest.TestCase):
    def test_live_requires_both_matching_json_and_html(self):
        expected = r.normalize_payload(fixture(), NOW)
        for payload, html, expected_match in [
            (expected, r.render_section(expected), True),
            ({"checked_at": None}, r.render_section(expected), False),
            (expected, r.render_section({"checked_at": None}), False),
        ]:
            with self.subTest(match=expected_match):
                def fetch(url):
                    return json.dumps(payload).encode() if "/data/" in url else html.encode()
                self.assertEqual(v.live_matches(expected, fetch), expected_match)


if __name__ == "__main__": unittest.main()
