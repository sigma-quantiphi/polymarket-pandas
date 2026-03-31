"""
Accounting Snapshot — Download and display user portfolio CSVs

Downloads the accounting snapshot ZIP for a user address and prints
each CSV as a DataFrame.

Requires environment variables (or a .env file):
    POLYMARKET_ADDRESS

Usage:
    python examples/accounting_snapshot.py
    python examples/accounting_snapshot.py 0xSomeOtherAddress
"""

from __future__ import annotations

import sys

import pandas as pd
from dotenv import load_dotenv

from polymarket_pandas import PolymarketPandas

load_dotenv()
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 20)

client = PolymarketPandas()
user = sys.argv[1] if len(sys.argv) > 1 else client.address

if not user:
    print("No address. Set POLYMARKET_ADDRESS or pass one as argument.")
    sys.exit(1)

print(f"Downloading accounting snapshot for {user} ...\n")
snapshot = client.get_accounting_snapshot(user)

for name, df in snapshot.items():
    print(f"=== {name.upper()} ({len(df)} rows, {len(df.columns)} cols) ===")
    print(df.to_markdown(index=False))
    print(df.dtypes)
    print()
