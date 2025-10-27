import asyncio
import orjson

import pandas as pd
import websockets

# Asset IDs for the BTC Up/Down market outcomes
UP_ASSET_ID = (
    "18091254444098592262784786533322521322014981925213197475982909617011905121307"
)
DOWN_ASSET_ID = (
    "38057471018344495140196614080825029304111223533996701043232392861721202499736"
)
ASSET_IDS = [UP_ASSET_ID, DOWN_ASSET_ID]
WS_URI = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


def parse_orderbook(data: dict | list) -> pd.DataFrame:
    bids = pd.json_normalize(
        data,
        record_path="bids",
        meta=[
            "market",
            "asset_id",
            "hash",
            "timestamp",
            "event_type",
        ],
    )
    asks = pd.json_normalize(
        data,
        record_path="asks",
        meta=[
            "market",
            "asset_id",
            "hash",
            "timestamp",
            "event_type",
        ],
    )
    bids["side"] = "bids"
    asks["side"] = "bids"
    data = pd.concat([bids, asks], ignore_index=True)
    return data


async def listen_to_trades():
    async with websockets.connect(WS_URI) as websocket:
        # Subscribe to the market channel
        subscription = {"type": "market", "assets_ids": ASSET_IDS}
        await websocket.send(orjson.dumps(subscription))
        print("Subscribed to trades for BTC Up/Down market.")

        async for message in websocket:
            try:
                data = orjson.loads(message)
                if isinstance(data, dict):
                    if data.get("event_type") == "price_change":
                        data = pd.json_normalize(
                            data,
                            record_path="price_changes",
                            meta=["market", "timestamp", "event_type"],
                        )
                    elif data.get("event_type") == "book":
                        data = parse_orderbook(data)
                    # elif data.get("event_type") == "trade":
                    #     data = parse_orderbook(data)
                    # elif data.get("event_type") == "order":
                    #     data = parse_orderbook(data)
                elif isinstance(data, list) and all(
                    [x["event_type"] == "book" for x in data]
                ):
                    data = parse_orderbook(data)
                print(data)
            except Exception as e:
                print(f"Received invalid JSON: {e}")


# Run the script
if __name__ == "__main__":
    asyncio.run(listen_to_trades())
