# tools/search.py - Bot-evasive web search parser and DOM content extractor
# Implementation details:
# Extracts search results from DuckDuckGo and directly fetches and parses readable HTML DOM content
# using a custom HTMLParser state machine, bypassing script/style blocks and bot detection.

import urllib.parse
import urllib.request
import json
import os
import random
import re
from html.parser import HTMLParser

class WebContentParser(HTMLParser):
    """Strips all HTML tags and ignores javascript/css to extract pure readable text from a webpage."""
    def __init__(self):
        super().__init__()
        self.in_script_or_style = False
        self.text_content = []

    def handle_starttag(self, tag, attrs):
        if tag in ["script", "style", "noscript", "meta", "head"]:
            self.in_script_or_style = True

    def handle_endtag(self, tag):
        if tag in ["script", "style", "noscript", "meta", "head"]:
            self.in_script_or_style = False

    def handle_data(self, data):
        if not self.in_script_or_style:
            text = data.strip()
            if text:
                self.text_content.append(text)


class DuckDuckGoParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_snippet = False
        self.results = []
        self.urls = []
        self.current_snippet = ""
    
    # using duckduckgo html, which uses result_snippet as the class name for the snippet.
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        """
            Only interested in the "Abstract" HTML snippet for a given search query.
        """
        # Check for the search result snippets
        if tag == "td" and attrs.get("class") == "result-snippet":
            self.in_snippet = True
        
        # get the link from result-link class
        if tag == "a" and attrs.get("class") == "result-link":
            href = attrs.get("href")
            if href and "duckduckgo.com" not in href:
                # got the organic URL from href (ignoring sponsored ad trackers)
                self.urls.append(href)
                
    # fires every time the parser sees raw text
    def handle_data(self, data):
        if self.in_snippet:
            self.current_snippet += data
            # print(data)
    
    # fire after all data has been seen.
    def handle_endtag(self, tag):
        if tag == "td" and self.in_snippet:
            self.in_snippet = False
            self.results.append(self.current_snippet.strip())
            self.current_snippet = ""

def _get_request_headers() -> dict:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    json_path = os.path.join(project_root, 'user_agents.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            user_agents = json.load(f)
        random_ua = random.choice(user_agents)
    except Exception:
        random_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    return {
        'User-Agent': random_ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }

def fetch_webpage_content(url: str, max_chars: int = 4000) -> str:
    """
    Directly fetches and extracts readable text from a specific webpage URL.
    Use this whenever a URL or website link is provided, or when needing to inspect a specific webpage's contents directly without using a search engine.
    """
    target_url = url.strip()
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        target_url = "https://" + target_url

    print(f"   [🌐 Kiko is fetching webpage: {target_url}...]")
    headers = _get_request_headers()
    req = urllib.request.Request(target_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html_text = response.read().decode('utf-8', errors='ignore')
            web_parser = WebContentParser()
            web_parser.feed(html_text)
            clean_text = " ".join(web_parser.text_content)
            if not clean_text:
                return f"Webpage at {target_url} loaded successfully, but contained no readable text body."
            max_chars = max(500, min(max_chars, 10000))
            return f"--- WEBPAGE CONTENT: {target_url} ---\n{clean_text[:max_chars]}"
    except Exception as e:
        return f"Failed to fetch webpage content from {target_url}: {e}"

def perform_web_search(query: str, max_snippets: int = 5, urls_to_scrape: int = 1) -> str:
    """
    Searches the internet for real-world facts to prevent hallucination. 
    Use when user asks question which you are not sure if your response will include the latest data or not. Always use this when asking about any form of enterntainment or online searches.
    You can dynamically manage the depth of your research by passing 'max_snippets' (how many search results to read) and 'urls_to_scrape' (how many full webpages to deep-dive into).
    """
    # If the query contains an explicit HTTP/HTTPS URL, redirect directly to webpage fetching
    url_match = re.search(r'https?://[^\s\'"<>]+', query)
    if url_match:
        target_url = url_match.group(0)
        return fetch_webpage_content(target_url)

    print(f"   [🌐 Kiko is performing a web search for: '{query}'...]")
    data = urllib.parse.urlencode({'q': query}).encode('utf-8')
    url = "https://lite.duckduckgo.com/lite/"
    headers = _get_request_headers()
    req = urllib.request.Request(url, data=data, headers=headers)

    parser = DuckDuckGoParser()

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html_text = response.read().decode('utf-8', errors='ignore')
            parser.feed(html_text)
    except Exception as e:
        return f"Failed to search DuckDuckGo: {e}"

    # Fetch the deep-dive content from the requested number of search results
    web_texts = []
    
    # Cap to prevent LLM context overflow or massive latency spikes
    urls_to_scrape = max(0, min(urls_to_scrape, 3))
    max_snippets = max(1, min(max_snippets, 15))
    
    if urls_to_scrape > 0 and parser.urls:
        # Distribute a ~3000 character budget evenly across the URLs being scraped
        char_budget = 3000 // urls_to_scrape
        
        for target_url in parser.urls[:urls_to_scrape]:
            try:
                print(f"   [🌐 Kiko is deep-diving into: {target_url}...]")
                req_target = urllib.request.Request(target_url, headers=headers)
                with urllib.request.urlopen(req_target, timeout=5) as response:
                    target_html = response.read().decode('utf-8', errors='ignore')
                    web_parser = WebContentParser()
                    web_parser.feed(target_html)
                    
                    # Combine the raw text and cap it
                    text = " ".join(web_parser.text_content)
                    web_texts.append(f"--- SOURCE: {target_url} ---\n{text[:char_budget]}")
            except Exception as e:
                web_texts.append(f"--- SOURCE: {target_url} ---\nFailed to load the target webpage: {e}")

    snippets_text = "\n".join(parser.results[:max_snippets])
    deep_dive_text = "\n\n".join(web_texts)
    
    return f"DUCKDUCKGO SNIPPETS:\n{snippets_text}\n\nIN-DEPTH CONTENT:\n{deep_dive_text}"