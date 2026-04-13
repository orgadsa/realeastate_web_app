from scraper.parsers.yad2 import Yad2Parser
from scraper.parsers.madlan import MadlanParser

PARSERS = {
    "yad2": Yad2Parser,
    "madlan": MadlanParser,
}


def get_parser_for_url(url: str):
    """Return the appropriate parser instance based on the URL domain."""
    url_lower = url.lower()
    if "yad2.co.il" in url_lower:
        return Yad2Parser()
    if "madlan.co.il" in url_lower:
        return MadlanParser()
    raise ValueError(
        f"Unsupported URL: {url}. Supported sites: yad2.co.il, madlan.co.il"
    )
