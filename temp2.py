import os

import pandas as pd
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, BookParams
from dotenv import load_dotenv
from py_clob_client.constants import AMOY


load_dotenv()


def main():
    host = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
    key = os.getenv("PK")
    creds = ApiCreds(
        api_key=os.getenv("CLOB_API_KEY"),
        api_secret=os.getenv("CLOB_SECRET"),
        api_passphrase=os.getenv("CLOB_PASS_PHRASE"),
    )
    chain_id = AMOY
    client = ClobClient(host, key=key, chain_id=chain_id, creds=creds)
    markets = client.get_markets()
    markets = pd.DataFrame(markets["data"])
    print(markets.columns)
    resp = client.get_midpoints(
        params=[
            BookParams(token_id=markets.iloc[0]["token_id"]),
            # BookParams(
            #     token_id="52114319501245915516055106046884209969926127482827954674443846427813813222426"
            # ),
        ]
    )
    print(resp)
    print("Done!")


main()
