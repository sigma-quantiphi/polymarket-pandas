"""
Merge Positions — Convert Yes + No tokens back into USDC.e

Merges equal amounts of both outcome tokens for a market back into
USDC.e collateral on Polygon.  You must already hold both outcomes
(e.g. from buying both sides, or from a prior split).

  1 Yes token + 1 No token  →  1 USDC.e

Requirements:
    pip install "polymarket-pandas[ctf]"

Create a .env file (see .env.example) with:
    POLYMARKET_ADDRESS      — Polymarket proxy wallet address
    POLYMARKET_PRIVATE_KEY  — EOA private key (signs on-chain txs)
    POLYMARKET_RPC_URL      — Polygon RPC (default: https://polygon-rpc.com)

Usage:
    # Auto-detect mergeable positions and merge the first one found:
    python examples/merge_positions.py

    # Merge a specific market by condition ID:
    python examples/merge_positions.py --condition-id 0x48d0d1...

    # Dry run (show what would be merged without sending a tx):
    python examples/merge_positions.py --dry-run
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from polymarket_pandas import PolymarketPandas


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge Yes+No tokens back into USDC.e")
    parser.add_argument(
        "--condition-id",
        help="Condition ID of the market to merge. If omitted, auto-detects from positions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without sending a transaction.",
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

    # ── 1. Fetch mergeable positions ──────────────────────────────────

    print(f"Fetching mergeable positions for {user} ...")
    positions = client.get_positions(user=user)

    if positions.empty:
        print("No mergeable positions found. You need both Yes and No tokens in a market.")
        sys.exit(1)

    positions["mergeableSize"] = positions.groupby("conditionId")["size"].transform("min")

    print(f"Found {len(positions)} position rows.\n")

    # ── 2. Pick the target market ─────────────────────────────────────

    if args.condition_id:
        cid = args.condition_id
        market_positions = positions.loc[positions["conditionId"] == cid]
        if market_positions.empty:
            print(f"No positions found for condition ID: {cid}")
            print("Available condition IDs:")
            print(positions[["conditionId", "mergeableSize", "title"]].round(2))
            sys.exit(1)
    else:
        cid = positions.loc[positions["mergeableSize"].idxmax(), "conditionId"]
        market_positions = positions.loc[positions["conditionId"] == cid]

    # ── 3. Calculate merge amount ─────────────────────────────────────

    print(f"Market: {market_positions['title'].iloc[0]}")
    print(f"Condition ID: {cid}")

    for _, row in market_positions.iterrows():
        print(
            f"  {row['outcome']:>10}: {row['size']:.6f} tokens"
            f"  (mergeable: {row['mergeableSize']:.6f})"
        )

    merge_shares = market_positions["mergeableSize"].iloc[0]
    neg_risk = bool(market_positions["negativeRisk"].iloc[0])

    print(f"\nMerge amount: {merge_shares:.6f} shares")
    print(f"Neg-risk:     {neg_risk}")
    print(f"Contract:     {'NegRiskAdapter' if neg_risk else 'ConditionalTokens'}")

    if merge_shares <= 0:
        print("Nothing to merge (zero balance on one side).")
        sys.exit(1)

    # ── Estimate gas cost ─────────────────────────────────────────────

    try:
        est = client.merge_positions(
            condition_id=cid,
            amount_usdc=merge_shares,
            neg_risk=neg_risk,
            estimate=True,
        )
        print(f"\nGas estimate: {est['gas']:,} units @ {est['gasPrice'] / 1e9:.1f} gwei")
        print(f"Merge cost:   {est['costMatic']:.6f} MATIC")
        print(f"EOA balance:  {est['eoaBalance'] / 1e18:.6f} MATIC")

        if est["eoaBalance"] < est["costWei"]:
            print(
                f"\nInsufficient MATIC! Need ~{est['costMatic']:.6f},"
                f" have {est['eoaBalance'] / 1e18:.6f}."
            )
            sys.exit(1)
    except Exception as e:
        err = str(e)
        print(f"\nGas estimate failed: {err}")
        if "subtraction overflow" in err:
            print(
                "The contract reverted — your on-chain token"
                " balance may be less than the position size"
                " reported by the API (tokens locked in open"
                " orders are not mergeable)."
            )
            sys.exit(1)

    if args.dry_run:
        print("\n[Dry run] Would merge — exiting without sending tx.")
        sys.exit(0)

    # ── 4. Merge (auto-approves if needed) ───────────────────────────

    print(f"\nMerging {merge_shares:.6f} shares ...")
    merge_tx = client.merge_positions(
        condition_id=cid,
        amount_usdc=merge_shares,
        neg_risk=neg_risk,
        auto_approve=True,
    )
    # Response keys differ: direct tx returns txHash/status/blockNumber,
    # relayed tx returns transactionHash/transactionID/state.
    tx_hash = merge_tx.get("txHash") or merge_tx.get("transactionHash")
    print(f"Tx hash:      {tx_hash}")
    for key in ("status", "blockNumber", "gasUsed", "transactionID", "state"):
        if key in merge_tx:
            print(f"{key:>14}: {merge_tx[key]}")

    client.close()
    print("\nDone! USDC.e has been returned to your wallet.")


if __name__ == "__main__":
    main()
