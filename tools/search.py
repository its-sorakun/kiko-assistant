# have to go all through this just to ensure model doesn't hallucinates.
import urllib.parse
import urllib.request
import html.parser
import json
import random
import os

class DuckDuckGoParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_snippet = False
        self.results = []
        self.current_snippet = ""
    
    # using duckduckgo html, which uses result_snippet as the class name for the snippet.
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        """
            Only interested in the "Abstract" HTML snippet for a given search query.
        """
        if tag == "td" and attrs.get("class") == "result-snippet":
                self.in_snippet = True
                
    
    # fires every time the parser sees raw text
    def handle_data(self, data):
        if self.in_snippet:
            self.current_snippet += data
    
    # fire after all data has been seen.
    def handle_endtag(self, tag):
        if tag == "td" and self.in_snippet:
            self.in_snippet = False
            self.results.append(self.current_snippet.strip())
            self.current_snippet = ""

def perform_web_search(query: str) -> str:
    """Searches the internet for real-world facts to prevent hallucination. Use when user asks question which you are not sure if your response will include the latest data or not. Always use this when asking about any form of enterntainment(like anime, movies, games, etc) or when user asks to do an online search"""
    print(f"   [🌐 Kiko is performing a web search for: '{query}'...]")
    # encode the query for a POST request.
    data = urllib.parse.urlencode({'q': query}).encode('utf-8')
    url = "https://lite.duckduckgo.com/lite/"

    # Load user agents from JSON file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    ua_path = os.path.join(current_dir, 'user_agents.json')
    try:
        with open(ua_path, 'r') as f:
            user_agents = json.load(f)
        random_ua = random.choice(user_agents)
    except Exception:
        random_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'

    # make the request with duckduckgo headers.
    headers = {
        'User-Agent': random_ua,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive'
    }
    req = urllib.request.Request(url, data=data, headers=headers)

    parser = DuckDuckGoParser()

    # urlopen request. read data and decode it.
    with urllib.request.urlopen(req) as response:
        html_text = response.read().decode('utf-8', errors='ignore')
        # print(html_text)
    
    # feeds data to parser
    # print(parser.feed(html_text))
    parser.feed(html_text)

    # return the top 3 results
    # print("\n".join(parser.results[:5]))
    return "\n".join(parser.results[:5])

# perform_web_search("genshin impact latest version")