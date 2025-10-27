import os

import pandas as pd
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams

load_dotenv()
HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")
FUNDER = os.getenv("POLYMARKET_FUNDER")

client = ClobClient(
    HOST,  # The CLOB API endpoint
    key=PRIVATE_KEY,  # Your wallet's private key
    chain_id=CHAIN_ID,  # Polygon chain ID (137)
    signature_type=1,  # 1 for email/Magic wallet signatures
    funder=FUNDER,  # Address that holds your funds
)
client.set_api_creds(client.create_or_derive_api_creds())

trades = client.get_markets()
trades = pd.DataFrame(trades["data"])
print(trades.loc[trades["market_slug"].str.contains("crypto")])

trades = client.get_positions("")
print(pd.DataFrame(trades).asset_id)

# orders = client.cancel_all()
# print(orders)
# print(pd.DataFrame(orders["data"]).explode("tokens"))
