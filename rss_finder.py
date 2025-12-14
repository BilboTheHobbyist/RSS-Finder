import urllib.parse
import html5lib
import requests
import feedparser
from requests.exceptions import Timeout, RequestException

TIMEOUT = 5  # seconds

FEED_SUFFIXES = [
    'feed', 'feed/', 'rss', 'atom', 'feed.xml',
    '/feed', '/feed/', '/rss', '/atom', '/feed.xml',
    'index.atom', 'index.rss', 'index.xml', 'atom.xml', 'rss.xml',
    '/index.atom', '/index.rss', '/index.xml', '/atom.xml', '/rss.xml',
    '.rss', '/.rss', '?rss=1', '?feed=rss2',
]


def is_valid_feed(url, errors):
    """Validate feed URL using feedparser."""
    parsed = feedparser.parse(url)
    if parsed.bozo or not parsed.entries:
        errors.add("invalid_feed")
        return False
    return True


def find_feed(url):
    errors = set()

    try:
        response = requests.get(
            url,
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=TIMEOUT
        )
        html = response.text
        tree = html5lib.parse(html, namespaceHTMLElements=False)

        # base for relative URLs
        base = tree.findall('.//base')
        base_url = (
            base[0].attrib['href']
            if base and 'href' in base[0].attrib
            else url
        )

        # prioritize Atom over RSS
        links = (
            tree.findall("""head/link[@rel='alternate'][@type='application/atom+xml']""") +
            tree.findall("""head/link[@rel='alternate'][@type='application/rss+xml']""")
        )

        for link in links:
            href = link.attrib.get('href', '').strip()
            if href:
                feed_url = urllib.parse.urljoin(base_url, href)
                if is_valid_feed(feed_url, errors):
                    return feed_url, errors

        # heuristic search for common feed paths
        for suffix in FEED_SUFFIXES:
            try:
                potential_feed = urllib.parse.urljoin(base_url, suffix)
                response = requests.get(potential_feed, timeout=TIMEOUT)
                if response.status_code == 200:
                    if is_valid_feed(potential_feed, errors):
                        return potential_feed, errors
            except Timeout:
                errors.add("timeout")
            except RequestException:
                errors.add("network")

    except Timeout:
        errors.add("timeout")
    except RequestException:
        errors.add("network")

    return None, errors


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python rss_finder.py [URL]")
        sys.exit(1)

    url = sys.argv[1]
    feed_url, errors = find_feed(url)

    if feed_url:
        print(f"{url}: found feed - {feed_url}")

    if errors:
        print(f"{url}: no feed URL found", end='', flush=True)
        if "timeout" in errors:
            print(" - one or more requests timed out.")
        if "network" in errors:
            print(" - one or more network errors occurred.")
        if "invalid_feed" in errors:
            print(" - one or more invalid feed looking URLs.")