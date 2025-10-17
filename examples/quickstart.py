from polymarket_pandas.client import PolymarketPandasClient

client = PolymarketPandasClient()
df = client.get_markets_df(limit=20)
print(df.head())
