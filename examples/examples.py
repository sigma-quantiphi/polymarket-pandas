import pandas as pd
from polymarket_pandas.client import PolymarketPandas

client = PolymarketPandas()
df = []
offset = 141426
length_data = 500
while length_data == 500:
    tags = client.get_markets(offset=offset, limit=500)
    length_data = len(tags.index)
    df.append(tags)
    offset += 500
    print(tags.tail(1))
df = pd.concat(df, ignore_index=True)
print(df)


from py_clob_client.client import ClobClient

client = ClobClient(
    "https://clob.polymarket.com",
    key="0xYOUR_PRIVATE_KEY",
    chain_id=137,
    signature_type=0,
)
creds = client.create_or_derive_api_creds()
client.set_api_creds(creds)
