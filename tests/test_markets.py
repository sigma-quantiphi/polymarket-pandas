from polymarket_pandas import PolymarketPandas
import pandas as pd

def test_get_markets_returns_dataframe() -> None:
    c = PolymarketPandas()
    df = c.get_markets(limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert any(col in df.columns for col in ["id", "slug", "question", "title"])
