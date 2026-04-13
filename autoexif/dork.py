"""DuckDuckGo dork search to find document URLs on target domains."""

import random
import re
import time
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup

from autoexif.pipeline import USER_AGENTS

SKIP_DOMAINS = {"duckduckgo.com", "bing.com", "google.com", "google.de"}


def is_ad_url(url: str) -> bool:
    """Check if a URL is an ad/tracker redirect rather than an organic result."""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
    except ValueError:
        return True
    if not host:
        return True
    return any(d in host for d in SKIP_DOMAINS)


def duckduckgo_search(dork: str, limit: int) -> list[str]:
    """Scrape DuckDuckGo HTML search results for the given dork query."""
    urls: list[str] = []
    session = requests.Session()
    session.verify = False
    session.headers.update({"User-Agent": random.choice(USER_AGENTS)})

    page = 0
    max_pages = (limit // 10) + 3
    next_form_data = None
    retries = 0

    while len(urls) < limit and page < max_pages:
        if page == 0:
            print("[*] Querying DuckDuckGo...")
        else:
            print(f"[*] Querying DuckDuckGo (page {page + 1})...")

        try:
            if page == 0:
                resp = session.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": dork},
                    timeout=15,
                )
            else:
                resp = session.post(
                    "https://html.duckduckgo.com/html/",
                    data=next_form_data,
                    timeout=15,
                )
        except requests.RequestException as e:
            print(f"[!] Search request failed: {e}")
            break

        if resp.status_code == 202:
            retries += 1
            if retries > 2:
                print("[!] Rate limited too many times. Giving up.")
                break
            wait = 10 * retries
            print(f"[!] Rate limited by DuckDuckGo. Waiting {wait}s (attempt {retries}/2)...")
            time.sleep(wait)
            continue

        if resp.status_code != 200:
            print(f"[!] Unexpected status {resp.status_code}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        found_this_page = 0
        for result_div in soup.find_all("div", class_="web-result"):
            a_tag = result_div.find("a", class_="result__a", href=True)
            if not a_tag:
                continue

            href = a_tag["href"]
            match = re.search(r"[?&]uddg=([^&]+)", href)
            if match:
                url = unquote(match.group(1))
            elif href.startswith("http"):
                url = href
            else:
                continue

            if is_ad_url(url):
                continue

            if url.startswith("http") and url not in urls:
                urls.append(url)
                found_this_page += 1
                if len(urls) >= limit:
                    break

        if found_this_page == 0:
            print("[*] No more results found.")
            break

        print(f"[*] Found {found_this_page} URLs (total: {len(urls)}).")

        next_form = soup.find("form", class_="nav-link")
        if not next_form:
            break
        next_form_data = {}
        for inp in next_form.find_all("input", attrs={"name": True}):
            next_form_data[inp["name"]] = inp.get("value", "")

        page += 1
        delay = random.uniform(2, 5)
        print(f"[*] Sleeping {delay:.1f}s...")
        time.sleep(delay)

    print(f"[+] Total URLs collected: {len(urls)}")
    return urls[:limit]
