from dataclasses import dataclass


@dataclass
class SourceStatus:
    source_name: str
    status: str = "idle"
    last_scrape_time: str = ""
    post_count: int = 0
    error_message: str = ""
