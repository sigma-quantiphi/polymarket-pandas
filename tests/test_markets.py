import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from polymarket_pandas.client import PolymarketPandasClient
import pandas as pd

def test_get_markets_df_returns_dataframe():
    client = PolymarketPandasClient()
    df = client.get_markets_df(limit=5)
    # Basic checks
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "question" in df.columns
