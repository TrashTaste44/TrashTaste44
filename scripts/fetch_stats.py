"""Fetch aggregate profile stats; never persist tokens or repository identities."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(url, payload=None, token=None):
    headers = {"User-Agent": "TrashTaste44-profile", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=json.dumps(payload).encode() if payload else None, headers=headers)
    for attempt in range(3):
        try:
            with urlopen(req, timeout=45) as response:
                return response.read().decode()
        except HTTPError as error:
            if attempt == 2 or error.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"GitHub request failed (HTTP {error.code})") from None
            time.sleep(2 ** attempt)


QUERY = """
query Profile($login: String!, $from: DateTime!, $to: DateTime!, $cursor: String) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
    repositories(first: 100, after: $cursor, privacy: PUBLIC, isFork: false,
                 ownerAffiliations: [OWNER], orderBy: {field: NAME, direction: ASC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
          pageInfo { hasNextPage }
          edges { size node { name } }
        }
      }
    }
  }
}
"""


def api_stats(login, start, end, token):
    cursor, languages, days = None, Counter(), {}
    until = min(datetime.combine(end, datetime.max.time(), tzinfo=timezone.utc),
                datetime.now(timezone.utc)).isoformat(timespec="seconds").replace("+00:00", "Z")
    while True:
        result = json.loads(request("https://api.github.com/graphql", {
            "query": QUERY,
            "variables": {"login": login, "from": start.isoformat() + "T00:00:00Z",
                          "to": until, "cursor": cursor},
        }, token))
        if result.get("errors") or not result.get("data", {}).get("user"):
            raise RuntimeError("GitHub GraphQL could not return complete profile stats")
        user = result["data"]["user"]
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for day in week["contributionDays"]:
                if start.isoformat() <= day["date"] <= end.isoformat():
                    days[day["date"]] = day["contributionCount"]
        repositories = user["repositories"]
        for repo in repositories["nodes"]:
            if repo["languages"]["pageInfo"]["hasNextPage"]:
                raise RuntimeError("A repository has over 100 languages; refusing incomplete totals")
            for edge in repo["languages"]["edges"]:
                languages[edge["node"]["name"]] += edge["size"]
        if not repositories["pageInfo"]["hasNextPage"]:
            break
        next_cursor = repositories["pageInfo"]["endCursor"]
        if not next_cursor or next_cursor == cursor:
            raise RuntimeError("Repository pagination did not advance")
        cursor = next_cursor
    return days, languages


class CalendarParser(HTMLParser):
    """Read counts from GitHub's public contribution tooltips, never color levels."""

    def __init__(self):
        super().__init__()
        self.dates, self.counts = {}, {}
        self.tip, self.parts = None, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("data-date") and attrs.get("id"):
            self.dates[attrs["id"]] = attrs["data-date"]
        if tag == "tool-tip":
            self.tip, self.parts = attrs.get("for"), []

    def handle_data(self, data):
        if self.tip:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tip:
            match = re.search(r"\b(No|[\d,]+) contributions? on\b", " ".join(self.parts))
            if match:
                value = match.group(1)
                self.counts[self.tip] = 0 if value == "No" else int(value.replace(",", ""))
            self.tip = None

    def days(self):
        return {day: self.counts[key] for key, day in self.dates.items() if key in self.counts}


def collect(login, end, public_calendar_only=False):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", login):
        raise ValueError("Invalid GitHub username")
    start = end - timedelta(days=29)
    if public_calendar_only:
        parser = CalendarParser()
        parser.feed(request(f"https://github.com/users/{login}/contributions?from={start}&to={end}"))
        days, languages = parser.days(), {}
        language_status = "pending"
        source = "GitHub public contribution calendar"
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise RuntimeError("Set GITHUB_TOKEN or GH_TOKEN to read the GitHub GraphQL API")
        days, languages = api_stats(login, start, end, token)
        language_status, source = "complete", "GitHub GraphQL API"
    expected = [(start + timedelta(days=n)).isoformat() for n in range(30)]
    if any(day not in days for day in expected):
        raise RuntimeError("GitHub did not return all 30 daily counts; existing assets are preserved")
    return {
        "username": login,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "contributions": [{"date": day, "count": days[day]} for day in expected],
        "languages": [{"name": name, "bytes": size} for name, size in
                      sorted(languages.items(), key=lambda pair: (-pair[1], pair[0]))],
        "language_status": language_status,
        "language_scope": "Public owned non-fork repositories; share of GitHub language bytes",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="TrashTaste44")
    parser.add_argument("--output", type=Path, default=Path("assets/profile-stats.json"))
    parser.add_argument("--end-date", type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument("--public-calendar-only", action="store_true",
                        help="Bootstrap real counts without the API; explicitly mark languages pending")
    args = parser.parse_args()
    stats = collect(args.username, args.end_date, args.public_calendar_only)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(json.dumps(stats, indent=2) + "\n")
    temporary.replace(args.output)
    print(f"Fetched {len(stats['contributions'])} daily counts; languages: {stats['language_status']}")


if __name__ == "__main__":
    main()
