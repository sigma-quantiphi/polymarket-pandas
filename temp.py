from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType, PostOrdersArgs
from py_clob_client.order_builder.constants import BUY


host: str = "https://clob.polymarket.com"
key: str = (
    ""  ##This is your Private Key. Export from https://reveal.magic.link/polymarket or from your Web3 Application
)
chain_id: int = 137  # No need to adjust this
POLYMARKET_PROXY_ADDRESS: str = (
    ""  # This is the address listed below your profile picture when using the Polymarket site.
)

# Select from the following 3 initialization options to matches your login method, and remove any unused lines so only one client is initialized.


### Initialization of a client using a Polymarket Proxy associated with an Email/Magic account. If you login with your email use this example.
client = ClobClient(
    host, key=key, chain_id=chain_id, signature_type=1, funder=POLYMARKET_PROXY_ADDRESS
)

### Initialization of a client using a Polymarket Proxy associated with a Browser Wallet(Metamask, Coinbase Wallet, etc)
client = ClobClient(
    host, key=key, chain_id=chain_id, signature_type=2, funder=POLYMARKET_PROXY_ADDRESS
)

### Initialization of a client that trades directly from an EOA.
client = ClobClient(host, key=key, chain_id=chain_id)

## Create and sign a limit order buying 100 YES tokens for 0.50c each
# Refer to the Markets API documentation to locate a tokenID: https://docs.polymarket.com/developers/gamma-markets-api/get-markets

client.set_api_creds(client.create_or_derive_api_creds())

resp = client.post_orders(
    [
        PostOrdersArgs(
            # Create and sign a limit order buying 100 YES tokens for 0.50 each
            order=client.create_order(
                OrderArgs(
                    price=0.01,
                    size=5,
                    side=BUY,
                    token_id="88613172803544318200496156596909968959424174365708473463931555296257475886634",
                )
            ),
            orderType=OrderType.GTC,  # Good 'Til Cancelled
        ),
        PostOrdersArgs(
            # Create and sign a limit order selling 200 NO tokens for 0.25 each
            order=client.create_order(
                OrderArgs(
                    price=0.01,
                    size=5,
                    side=BUY,
                    token_id="93025177978745967226369398316375153283719303181694312089956059680730874301533",
                )
            ),
            orderType=OrderType.GTC,  # Good 'Til Cancelled
        ),
    ]
)
print(resp)
print("Done!")
