def match_keywords(title: str, content: str, keywords: list[str]) -> list[str]:
    """Return list of keywords that appear in title or content."""

    text = (title + " " + content).lower()
    return [kw for kw in keywords if kw.lower() in text]
