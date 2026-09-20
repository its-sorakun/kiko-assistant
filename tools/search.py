# have to go all through this just to ensure model doesn't hallucinates.
import urllib.parse
import urllib.request
import html.parser

class DuckDuckGoParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_snippet = False
        self.results = []
    
    # using duckduckgo html, which uses result_snippet as the class name for the snippet.
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        """
            Only interested in the "Abstract" HTML snippet for a given search query.
        """
        if tag == "a" and attrs.get("class") == "result__snippet":
                self.in_snippet = True
    
    # fires every time the parser sees raw text
    def handle_data(self, data):
        if self.in_snippet:
            self.results.append(data.strip())
    
    # fire after all data has been seen.
    def handle_endtag(self, tag):
        if tag == "a" and self.in_snippet:
            self.in_snippet = False

def perform_web_search(query: str) -> str:
    """Searches the internet for real-world facts to prevent hallucination. Use when user asks question which you are not sure if your response will include the latest data or not. Always use this when asking about any form of enterntainment(like anime, movies, games, etc)"""
    # encode the query properly.
    encoded_query = urllib.parse.quote(query)
    # encoded_query = "python"
    url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

    # make the request with duckduckgo headers.
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    parser = DuckDuckGoParser()

    # urlopen request. read data and decode it.
    with urllib.request.urlopen(req) as response:
        html_text = response.read().decode('utf-8', errors='ignore')
        # print(html_text)
    
    # feeds data to parser
    print(parser.feed(html_text))
    
    # return the top 3 results
    print("\n".join(parser.results[:3]))
    return "\n".join(parser.results[:3])

perform_web_search("what is python")