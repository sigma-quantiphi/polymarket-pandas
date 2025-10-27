import json, time, threading

import orjson
import pandas as pd
from websocket import WebSocketApp  # pip install websocket-client

WS_URL = "wss://ws-live-data.polymarket.com"
df = pd.DataFrame(
    columns=["source", "timestamp", "full_accuracy_value", "symbol", "value"]
)


def on_open(ws):
    sub = {
        "action": "subscribe",
        "subscriptions": [
            {
                "topic": "crypto_prices_chainlink",
                "type": "*",
                # "filters": {"symbol": "btc/usd"}
            },
            {
                "topic": "crypto_prices",
                "type": "update",
            },
        ],
    }
    ws.send(orjson.dumps(sub))

    # keep-alive pings every ~5s
    def ping():
        while True:
            time.sleep(5)
            try:
                ws.send("PING")
            except:
                break

    threading.Thread(target=ping, daemon=True).start()


def on_message(ws, msg):
    global df
    data = orjson.loads(msg)
    data["payload"]["source"] = data["topic"]
    data = data["payload"]
    data["source"] = (
        data["source"]
        .replace("crypto_prices_chainlink", "chainlink")
        .replace("crypto_prices", "binance")
    )
    data["timestamp"] = pd.Timestamp(data["timestamp"], unit="ms", tz="UTC")
    data["full_accuracy_value"] = float(data["full_accuracy_value"])
    df.loc[len(df)] = data
    print(df)


def on_error(ws, err):
    print("WS error:", err)


def on_close(ws, code, reason):
    print("WS closed:", code, reason)


ws = WebSocketApp(
    WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close
)
ws.run_forever()
