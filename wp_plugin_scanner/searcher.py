import requests
from .config import DEFAULT_TIMEOUT, SLUG_RE, SEARCH_URL_TMPL, MAX_SEARCH_RESULTS

class PluginSearcher:
    """Search WordPress.org for plugin slugs by keyword."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def search(self, keyword: str, limit: int = MAX_SEARCH_RESULTS) -> list[str]:
        keyword = keyword.strip()
        if not keyword:
            return []
        slugs: list[str] = []
        page = 1
        while len(slugs) < limit:
            url = SEARCH_URL_TMPL.format(kw=requests.utils.quote(keyword), page=page)
            try:
                r = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                r.raise_for_status()
            except requests.RequestException as e:
                raise RuntimeError(f"Search failed: {e}") from e
            matches = SLUG_RE.findall(r.text)
            if not matches:
                break
            for m in matches:
                if m not in slugs:
                    slugs.append(m)
                    if len(slugs) >= limit:
                        break
            page += 1
        return slugs
