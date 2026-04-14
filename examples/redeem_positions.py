"""
Redeem Positions — Claim USDC.e for winning outcome tokens

After a Polymarket market resolves, winning outcome tokens can be
redeemed for USDC.e at $1 per share. Losing tokens are worthless.

  1 winning Yes (or No) token  →  1 USDC.e

Unlike merging (which requires both Yes and No), redeeming only
requires that the market has resolved and you hold the winning side.

Supports both standard binary markets (ConditionalTokens) and
neg-risk multi-outcome markets (NegRiskAdapter) — the example
auto-detects the market type and fills in the token amounts from
the positions API.

Requirements:
    pip install "polymarket-pandas[ctf]"

Create a .env file (see .env.example) with:
    POLYMARKET_ADDRESS      — Polymarket proxy wallet address
    POLYMARKET_PRIVATE_KEY  — EOA private key (signs on-chain txs)
    POLYMARKET_RPC_URL      — Polygon RPC (default: https://polygon-rpc.com)

Usage:
    # Auto-detect redeemable positions and redeem the largest one:
    python examples/redeem_positions.py

    # Redeem a specific market by condition ID:
    python examples/redeem_positions.py --condition-id 0x48d0d1...

    # Redeem ALL redeemable positions in one go:
    python examples/redeem_positions.py --all

    # Dry run (show what would be redeemed without sending a tx):
    python examples/redeem_positions.py --dry-run
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from polymarket_pandas import PolymarketPandas


def redeem_one(client: PolymarketPandas, cid: str, market_rows, dry_run: bool) -> None:
    """Estimate + redeem a single market. market_rows is a DataFrame slice
    for one condition_id (1 or 2 rows, one per outcome)."""
    first = market_rows.iloc[0]
    neg_risk = bool(first["negativeRisk"])
    total_value = market_rows["currentValue"].sum()

    print(f"\nMarket:       {first['title']}")
    print(f"Condition ID: {cid}")
    print(f"Neg-risk:     {neg_risk}")
    print(f"Value:        ${total_value:.2f}")
    for _, r in market_rows.iterrows():
        print(f"  {r['outcome']:>10}: {r['size']:.6f} tokens  (${r['currentValue']:.2f})")

    # Build neg-risk amounts array if needed: [yes_amount, no_amount]
    # Polymarket convention: outcome index 0 = Yes, 1 = No
    redeem_kwargs: dict = {"condition_id": cid, "neg_risk": neg_risk}
    if neg_risk:
        amounts = [0, 0]
        for _, r in market_rows.iterrows():
            idx = 0 if r["outcome"].lower() in ("yes", "positive", "over", "up") else 1
            amounts[idx] = int(r["size"] * 1e6)
        redeem_kwargs["amounts"] = amounts
        print(f"Amounts:      [yes={amounts[0]}, no={amounts[1]}]")

    # ── Estimate gas cost ─────────────────────────────────────────────
    try:
        est = client.redeem_positions(**redeem_kwargs, estimate=True)
        print(f"Gas estimate: {est['gas']:,} units @ {est['gasPrice'] / 1e9:.1f} gwei")
        print(f"Redeem cost:  {est['costMatic']:.6f} MATIC")
        print(f"EOA balance:  {est['eoaBalance'] / 1e18:.6f} MATIC")

        if est["eoaBalance"] < est["costWei"]:
            print(
                f"  Insufficient MATIC! Need ~{est['costMatic']:.6f}, "
                f"have {est['eoaBalance'] / 1e18:.6f}."
            )
            return
    except Exception as e:
        print(f"  Gas estimate failed: {str(e)[:200]}")
        return

    if dry_run:
        print("  [Dry run] Would redeem — skipping tx.")
        return

    # ── Redeem ────────────────────────────────────────────────────────
    print("  Redeeming ...")
    tx = client.redeem_positions(**redeem_kwargs)
    # Response keys differ: direct tx returns txHash/status/blockNumber,
    # relayed tx returns transactionHash/transactionID/state.
    tx_hash = tx.get("txHash") or tx.get("transactionHash")
    print(f"  Tx hash: {tx_hash}")
    for key in ("status", "blockNumber", "gasUsed", "transactionID", "state"):
        if key in tx:
            print(f"  {key}: {tx[key]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Redeem winning outcome tokens for USDC.e")
    parser.add_argument(
        "--condition-id",
        help="Condition ID of the market to redeem. Omit to auto-pick largest.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Redeem every redeemable position.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be redeemed without sending a transaction.",
    )
    args = parser.parse_args()

    client = PolymarketPandas()
    user = client.address
    if not user:
        print(
            "Error: POLYMARKET_ADDRESS is required."
            " Set it in .env or pass address= to the constructor."
        )
        sys.exit(1)

    # ── Check EOA MATIC balance ─────────────────────────────────────
    client._require_web3()
    eoa = client._eoa_address()
    eoa_balance = client._w3.eth.get_balance(eoa)
    print(f"EOA:     {eoa}")
    print(f"MATIC:   {eoa_balance / 1e18:.6f}\n")

    # ── 1. Fetch redeemable positions ─────────────────────────────────
    print(f"Fetching redeemable positions for {user} ...")
    positions = client.get_positions(user=user, redeemable=True, sizeThreshold=0)

    if positions.empty:
        print("No redeemable positions found. Markets must be resolved first.")
        sys.exit(0)

    # Sort markets by total redeemable value (desc)
    totals = positions.groupby("conditionId")["currentValue"].sum().sort_values(ascending=False)
    print(f"Found {len(totals)} redeemable market(s):\n")
    for cid, total in totals.items():
        first_title = positions.loc[positions["conditionId"] == cid, "title"].iloc[0]
        print(f"  ${total:>8.2f}  {cid[:20]}...  {first_title}")

    # ── 2. Pick the target(s) ─────────────────────────────────────────
    if args.all:
        target_cids = list(totals.index)
    elif args.condition_id:
        if args.condition_id not in totals.index:
            print(f"\nNo redeemable position for condition ID: {args.condition_id}")
            sys.exit(1)
        target_cids = [args.condition_id]
    else:
        target_cids = [totals.index[0]]

    # ── 3. Redeem each target ─────────────────────────────────────────
    for cid in target_cids:
        market_rows = positions.loc[positions["conditionId"] == cid]
        redeem_one(client, cid, market_rows, args.dry_run)

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
