#!/usr/bin/env python3
"""Refresh only validated Google Scholar metrics; never log provider responses/URLs."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import urllib.parse
import urllib.request

AUTHOR_ID = "jtLduoQAAAAJ"  # Existing, published Google Scholar profile link.
PROFILE_URL = f"https://scholar.google.com/citations?hl=en&user={AUTHOR_ID}"
ROOT = Path(__file__).resolve().parents[1]
START = "  <!-- BEGIN SCHOLAR METRICS -->"
END = "  <!-- END SCHOLAR METRICS -->"
MAX_RESPONSE_BYTES = 2_000_000


class RefreshError(Exception):
    """Only fixed, safe-to-log messages belong in this exception."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RefreshError("Unexpected provider redirect; previous figures retained.")


def fetch_payload(api_key):
    if not api_key or not api_key.strip():
        raise RefreshError("SERPAPI_API_KEY is missing; previous figures retained.")
    query = urllib.parse.urlencode({
        "engine": "google_scholar_author", "author_id": AUTHOR_ID,
        "hl": "en", "no_cache": "true", "api_key": api_key,
    })
    request = urllib.request.Request(
        "https://serpapi.com/search.json?" + query,
        headers={"Accept": "application/json", "User-Agent": "DavidSlompSiteMetrics/1.0"},
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=45) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RefreshError("Provider response too large; previous figures retained.")
        return json.loads(raw)
    except RefreshError:
        raise
    except Exception:
        # HTTP errors, URLs, response bodies and exception text may contain the key.
        raise RefreshError("Provider request failed; check account/quota/connectivity. Previous figures retained.") from None


def counter(value):
    if type(value) is not int or not 0 <= value <= 1_000_000_000:
        raise RefreshError("Invalid citation counter; previous figures retained.")
    return value


def normalize_payload(payload, now):
    stage = "response object"
    try:
        if not isinstance(payload, dict) or "error" in payload:
            raise ValueError
        stage = "provider success status"
        if payload["search_metadata"]["status"] != "Success":
            raise ValueError
        stage = "profile ID and engine"
        params = payload["search_parameters"]
        if params["engine"] != "google_scholar_author" or params["author_id"] != AUTHOR_ID:
            raise ValueError
        stage = "author name"
        name = " ".join(payload["author"]["name"].split()).casefold()
        if name != "david slomp":
            raise ValueError
        stage = "citation table"
        table = payload["cited_by"]["table"]
        if not isinstance(table, list):
            raise ValueError
        metrics = {}
        recent_year = None
        for row in table:
            stage = "metric row names"
            if not isinstance(row, dict) or len(row) != 1:
                raise ValueError
            key, values = next(iter(row.items()))
            if key not in ("citations", "h_index", "i10_index") or key in metrics:
                raise ValueError
            stage = "all/recent column labels"
            if not isinstance(values, dict) or "all" not in values:
                raise ValueError
            recent_keys = [key for key in values if re.fullmatch(r"since_\d{4}", key)]
            if len(recent_keys) != 1 or len(values) != 2:
                raise ValueError
            stage = "recent since year"
            year = int(recent_keys[0][6:])
            if not 1900 <= year <= now.year or (recent_year is not None and year != recent_year):
                raise ValueError
            recent_year = year  # Read the provider's label; never assume a rolling year.
            all_count, recent = counter(values["all"]), counter(values[recent_keys[0]])
            stage = "recent versus all counters"
            if recent > all_count:
                raise ValueError
            metrics[key] = {"all": all_count, "recent": recent}
        stage = "required citation and h-index rows"
        if not {"citations", "h_index"}.issubset(metrics):
            raise ValueError
        stage = "mathematical counter bounds"
        for column in ("all", "recent"):
            if metrics["h_index"][column] ** 2 > metrics["citations"][column]:
                raise ValueError
            if "i10_index" in metrics and metrics["i10_index"][column] * 10 > metrics["citations"][column]:
                raise ValueError
        # Zero citations is valid only with zero h/i10 counters.
        if any(value["all"] > metrics["citations"]["all"] or value["recent"] > metrics["citations"]["recent"] for value in metrics.values()):
            raise ValueError
        return {
            "schema_version": 1, "author_id": AUTHOR_ID, "author_name": "David Slomp",
            "source": "Google Scholar via SerpApi", "profile_url": PROFILE_URL,
            "checked_at": now.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "recent_since": recent_year, "metrics": metrics,
        }
    except (KeyError, TypeError, ValueError, AttributeError):
        # Stage is a fixed code label, never response text or a field value.
        raise RefreshError(f"Scholar validation failed at {stage}; previous figures retained.") from None


def validate_snapshot(snapshot):
    """Validate stored data too, rather than only trusting a matching rendering."""
    try:
        if snapshot["schema_version"] != 1 or snapshot["author_id"] != AUTHOR_ID or snapshot["author_name"] != "David Slomp" or snapshot["profile_url"] != PROFILE_URL:
            raise ValueError
        if snapshot["checked_at"] is None:
            if snapshot["historical_snapshot"] != {
                "as_of": "2026-09", "citations_display": "1,200+", "h_index_display": "18",
                "recent_share_display": "Nearly 70%", "recent_since": 2021,
            }:
                raise ValueError
            return
        checked = dt.datetime.fromisoformat(snapshot["checked_at"].replace("Z", "+00:00"))
        if checked.tzinfo is None or checked.utcoffset() != dt.timedelta(0) or not snapshot["checked_at"].endswith("Z"):
            raise ValueError
        if checked > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
            raise ValueError
        table = [{key: {"all": values["all"], f'since_{snapshot["recent_since"]}': values["recent"]}} for key, values in snapshot["metrics"].items()]
        normalized = normalize_payload({
            "search_metadata": {"status": "Success"},
            "search_parameters": {"engine": "google_scholar_author", "author_id": AUTHOR_ID},
            "author": {"name": "David Slomp"}, "cited_by": {"table": table},
        }, checked)
        if normalized != snapshot:
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        raise RefreshError("Saved metrics schema or identity is invalid.") from None


def render_section(snapshot):
    checked_at = snapshot["checked_at"]
    if checked_at is None:
        # This is the site's pre-existing approximation, not a successful API check.
        title = "Google Scholar · September 2026 snapshot"
        note = "Historical figures; weekly refresh not yet verified."
        citations, h_index, recent_label, recent_value = "1,200+", "18", "Of citations received since 2021", "Nearly 70%"
    else:
        checked = dt.datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        date = f"{checked.day} {checked.strftime('%B %Y')}"
        title = "Google Scholar"
        note = f"Last successful check: {date} (UTC). Weekly schedule; figures may change."
        metrics = snapshot["metrics"]
        citations = f'{metrics["citations"]["all"]:,}'
        h_index = str(metrics["h_index"]["all"])
        recent_label = f'Of citations received since {snapshot["recent_since"]}'
        total = metrics["citations"]["all"]
        # Whole percentage is explicitly approximate; zero has no defined share.
        recent_value = f'About {metrics["citations"]["recent"] / total:.0%}' if total else "—"
    source = html.escape(PROFILE_URL, quote=True)
    return f'''{START}
  <section class="evidence-section" aria-labelledby="research-impact-title">
    <div class="container evidence-strip">
      <div class="evidence-intro">
        <h2 id="research-impact-title">Research impact</h2>
        <a href="{source}" target="_blank" rel="noopener noreferrer">{title}</a>
        <p class="scholar-status" data-scholar-checked-at="{checked_at or ''}">{note}</p>
      </div>

      <dl class="evidence-grid">
        <div class="evidence-item">
          <dt>Scholarly citations</dt>
          <dd>{citations}</dd>
        </div>
        <div class="evidence-item">
          <dt>h-index</dt>
          <dd>{h_index}</dd>
        </div>
        <div class="evidence-item">
          <dt>{recent_label}</dt>
          <dd>{recent_value}</dd>
        </div>
      </dl>
    </div>
  </section>
{END}'''


def updated_index(current, snapshot):
    if current.count(START) != 1 or current.count(END) != 1:
        raise RefreshError("Metrics markers missing or duplicated; previous figures retained.")
    begin, end = current.index(START), current.index(END) + len(END)
    if begin >= end:
        raise RefreshError("Metrics markers out of order; previous figures retained.")
    return current[:begin] + render_section(snapshot) + current[end:]


def write_outputs(root, snapshot):
    """Prepare both files before replacement; roll back on a local write failure.

    The workflow commits both together only after this function exits successfully.
    """
    paths = [root / "data/scholar-metrics.json", root / "index.html"]
    originals = [path.read_bytes() for path in paths]
    contents = [
        (json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n").encode(),
        updated_index(originals[1].decode(), snapshot).encode(),
    ]
    temps, changed = [], []
    try:
        for path, content in zip(paths, contents):
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as out:
                temps.append(Path(out.name))
                out.write(content)
                out.flush()
                os.fsync(out.fileno())
            os.chmod(temps[-1], 0o644)
        for index, path in enumerate(paths):
            os.replace(temps[index], path)
            changed.append(index)
    except OSError:
        for index in changed:
            paths[index].write_bytes(originals[index])
        raise RefreshError("Could not save metrics; previous figures retained.") from None
    finally:
        for path in temps:
            path.unlink(missing_ok=True)


def refresh(root=ROOT, api_key=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    snapshot = normalize_payload(fetch_payload(api_key), now)
    write_outputs(root, snapshot)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check generated HTML matches saved data; no network/key needed.")
    args = parser.parse_args()
    try:
        if args.check:
            snapshot = json.loads((ROOT / "data/scholar-metrics.json").read_text())
            validate_snapshot(snapshot)
            current = (ROOT / "index.html").read_text()
            if updated_index(current, snapshot) != current:
                raise RefreshError("Saved metrics and homepage are inconsistent.")
            print("Saved metrics and homepage match.")
        else:
            refresh(api_key=os.environ.get("SERPAPI_API_KEY"))
            print("Validated Google Scholar metrics saved. Publication still requires a successful Pages build.")
        return 0
    except RefreshError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Refresh could not complete; no publication attempted. Check saved files and configuration.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
