# have to go all through this just to ensure model doesn't hallucinates.
import urllib.parse
import urllib.request
import urllib.parse
import json
import os
import random
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
            if href:
                # print(href)
                # got the URL from href
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

def perform_web_search(query: str) -> str:
    """Searches the internet for real-world facts to prevent hallucination. Use when user asks question which you are not sure if your response will include the latest data or not. Always use this when asking about any form of enterntainment(like anime, movies, games, etc) or when user asks to do an online search"""
    print(f"   [🌐 Kiko is performing a web search for: '{query}'...]")
    data = urllib.parse.urlencode({'q': query}).encode('utf-8')
    url = "https://lite.duckduckgo.com/lite/"

    # Load user agents from JSON file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, 'user_agents.json')
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            user_agents = json.load(f)
        random_ua = random.choice(user_agents)
    except Exception as e:
        random_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    headers = {
        'User-Agent': random_ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }
    req = urllib.request.Request(url, data=data, headers=headers)

    parser = DuckDuckGoParser()

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html_text = response.read().decode('utf-8', errors='ignore')
            parser.feed(html_text)
    except Exception as e:
        return f"Failed to search DuckDuckGo: {e}"

    # Fetch the deep-dive content from the FIRST search result
    web_text = ""
    first_url = parser.urls[0] if parser.urls else None
    
    if first_url:
        try:
            print(f"   [🌐 Kiko is deep-diving into: {first_url}...]")
            req_target = urllib.request.Request(first_url, headers=headers)
            with urllib.request.urlopen(req_target, timeout=5) as response:
                target_html = response.read().decode('utf-8', errors='ignore')
                web_parser = WebContentParser()
                web_parser.feed(target_html)
                
                # Combine the raw text and cap it to ~3000 characters to prevent memory overflow
                web_text = " ".join(web_parser.text_content)
                web_text = web_text[:3000]
        except Exception as e:
            web_text = f"Failed to load the target webpage: {e}"

    snippets_text = "\n".join(parser.results[:5])
    
    return f"DUCKDUCKGO SNIPPETS:\n{snippets_text}\n\nIN-DEPTH CONTENT ({first_url}):\n{web_text}"

# print(perform_web_search("latest Odette build guide"))