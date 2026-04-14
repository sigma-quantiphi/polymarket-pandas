"""
Redeem Positions — Claim USDC.e for winning outcome tokens

After a Polymarket market resolves, winning outcome tokens can be
redeemed for USDC.e at $1 per share. Losing tokens are worthless.

  1 winning Yes (or No) token  →  1 USDC.e

Unlike merging (which requires both Yes and No), redeeming only
requires that the market has resolved and you hold the winning side.

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

Note:
    This example currently supports standard (binary) markets only.
    Neg-risk markets use a different redeem API on the NegRiskAdapter
    contract and are not yet supported by ``client.redeem_positions``.
"""

from __future__ import annotations

import argparse
import sys

from dotenv import load_dotenv

load_dotenv()

from polymarket_pandas import PolymarketPandas


def redeem_one(client: PolymarketPandas, cid: str, row, dry_run: bool) -> None:
    """Estimate + redeem a single market."""
    print(f"\nMarket:       {row['title']}")
    print(f"Condition ID: {cid}")
    print(f"Outcome:      {row['outcome']}  ({row['size']:.6f} tokens)")
    print(f"Value:        ${row['currentValue']:.2f}")
    print(f"Neg-risk:     {row['negativeRisk']}")

    if row["negativeRisk"]:
        print("  Skipping — neg-risk redemption not yet supported by client.redeem_positions.")
        return

    # ── Estimate gas cost ─────────────────────────────────────────────
    try:
        est = client.redeem_positions(condition_id=cid, estimate=True)
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
        print(f"  Gas estimate failed: {str(e)[:120]}")
        return

    if dry_run:
        print("  [Dry run] Would redeem — skipping tx.")
        return

    # ── Redeem ────────────────────────────────────────────────────────
    print("  Redeeming ...")
    tx = client.redeem_positions(condition_id=cid)
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

    # Collapse to one row per market (take the winning outcome)
    # The redeemable flag already filters to winning tokens only.
    positions = positions.sort_values("currentValue", ascending=False)
    print(f"Found {len(positions)} redeemable position(s):\n")
    print(
        positions[["conditionId", "outcome", "size", "currentValue", "title"]]
        .round(4)
        .to_string(index=False)
    )

    # ── 2. Pick the target(s) ─────────────────────────────────────────
    if args.all:
        targets = positions
    elif args.condition_id:
        targets = positions.loc[positions["conditionId"] == args.condition_id]
        if targets.empty:
            print(f"\nNo redeemable position for condition ID: {args.condition_id}")
            sys.exit(1)
    else:
        # Pick the most valuable one
        targets = positions.head(1)

    # ── 3. Redeem each target ─────────────────────────────────────────
    for _, row in targets.iterrows():
        redeem_one(client, row["conditionId"], row, args.dry_run)

    client.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
