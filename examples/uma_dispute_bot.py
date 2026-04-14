"""UMA resolution dispute bot — skeleton.

Polls Gamma for markets whose UMA proposal is currently live, checks the
proposed resolution against a user-supplied rule, and disputes when the
proposal is wrong.

Requires the ``ctf`` extra for web3:

    pip install polymarket-pandas[ctf]

Environment variables:

    POLYMARKET_PRIVATE_KEY  — EOA with MATIC (gas) + USDC.e (bond)
    POLYMARKET_RPC_URL      — optional custom Polygon RPC

*Dry-run by default.* Set ``LIVE=1`` to actually send dispute txs.
"""

from __future__ import annotations

import os

from polymarket_pandas import PolymarketPandas
from polymarket_pandas.mixins._uma import PRICE_YES

LIVE = os.environ.get("LIVE") == "1"


def should_dispute(market: dict, proposed_price: int) -> bool:
    """User rule: decide whether a proposal is wrong.

    Replace this with your own logic (external data source, model,
    manual allow-list, etc.).  Returning ``False`` skips the market.
    """
    # Example: dispute any proposal where the market's current CLOB
    # midpoint disagrees with the proposed outcome by more than 20¢.
    midpoint = float(market.get("lastTradePrice") or 0.5)
    proposed_yes = proposed_price == PRICE_YES
    if proposed_yes and midpoint < 0.3:
        return True
    if not proposed_yes and midpoint > 0.7:
        return True
    return False


def main() -> None:
    client = PolymarketPandas()

    # Gamma filters markets to those currently in the UMA resolution
    # window.  See ``get_markets`` ``uma_resolution_status`` in _gamma.py.
    markets = client.get_markets_all(
        uma_resolution_status="proposed",
        closed=False,
        limit=100,
    )
    if markets.empty:
        print("No markets with a live UMA proposal.")
        return

    for row in markets.itertuples(index=False):
        qid = getattr(row, "questionID", None)
        if not qid:
            continue
        neg_risk = bool(getattr(row, "negRisk", False))

        state = client.get_uma_state(qid, neg_risk=neg_risk)
        if state != "Proposed":
            continue

        req = client.get_oo_request(qid, neg_risk=neg_risk)
        proposed = req["proposedPrice"]
        print(
            f"{row.slug}  state={state}  proposed={proposed}  "
            f"expiresAt={req['expirationTime']}  bond={req['bond'] / 1e6:.2f} USDC"
        )

        if not should_dispute(row._asdict(), proposed):
            continue

        if not LIVE:
            print(f"  [dry-run] would dispute {qid}")
            continue

        receipt = client.dispute_price(qid, neg_risk=neg_risk)
        print(f"  disputed: tx={receipt.get('txHash')} status={receipt.get('status')}")


if __name__ == "__main__":
    main()
