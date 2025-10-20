from polymarket_pandas.polymarket_pandas import PolymarketPandas

def main() -> None:
    client = PolymarketPandas()
    df = client.get_markets(limit=20)
    print(df.head())

if __name__ == "__main__":
    main()
