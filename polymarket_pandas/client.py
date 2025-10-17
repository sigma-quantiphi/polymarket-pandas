import httpx
import pandas as pd

GAMMA_URL = "https://gamma-api.polymarket.com"

class PolymarketPandasClient:
    """Simple client to fetch public Polymarket data and return as Pandas DataFrames."""

    def __init__(self, timeout=30):
        self.client = httpx.Client(timeout=timeout)

    def get_markets_df(self, page=1, limit=100):
        """Fetch public markets and return as a DataFrame."""
        url = f"{GAMMA_URL}/markets?limit={limit}&page={page}"
        response = self.client.get(url)
        response.raise_for_status()

        data = response.json()  # This endpoint returns a list directly

        rows = []
        for m in data:
            rows.append({
                "id": m.get("id"),
                "question": m.get("question") or m.get("title"),
                "status": m.get("status"),
                "end_time": m.get("end_date") or m.get("closeTime"),
                "volume": m.get("volume"),
                "liquidity": m.get("liquidity"),
                "category": m.get("category"),
                "slug": m.get("slug"),
            })
        return pd.DataFrame(rows)
