# rs iroh

[rs](../code/rs.md)
[iroh documentation](https://docs.rs/iroh) · [iroh-gossip documentation](https://docs.rs/iroh-gossip)

- use `iroh = "1"` and rust 1.91 or later
- use `iroh-gossip` 0.101 with the matching `iroh` 1 release
- use endpoint vocabulary; do not use the removed node vocabulary
- treat an endpoint address as one endpoint ID plus one set of transport addresses
- read relay and direct addresses through accessors instead of storing parallel address models

## endpoint

- start with the `N0` preset when managed discovery and relay access are acceptable
- use `N0DisableRelay` when discovery is required without managed relays
- use `Minimal` or `Empty` only when the application owns the missing transport policy
- set the secret key, ALPNs, relay mode, bind address, and address lookup on the builder
- allow the `N0` address lookup to resolve endpoint IDs through DNS and pkarr
- expect WASM peers to lack local-network discovery
- self-host a relay when managed-relay policy does not meet the deployment contract

## gossip

### setup

- enable the `net` feature for network I/O; use `proto` only for the state machine
- attach gossip to a live endpoint and serve it through the router under the gossip ALPN
- route browser peers through a relay over WebSocket

### subscription

- use resolvable endpoint IDs as bootstrap peers; gossip does not discover peers
- use `subscribe_and_join()` when work must wait for one active neighbour
- use `subscribe()` only when immediate return and deferred connection are acceptable
- resubscribe when another view of an existing membership is required

### messages

- set one maximum message size for every peer; an oversized broadcast fails
- keep broadcast payloads within the configured limit; the default is 4096 bytes

### handles

- keep topic senders and receivers in application state because gossip does not enumerate handles
- treat the topic as left after every handle is dropped
- rebuild state after a lagged event because dropped messages are not delivered again

## operational limits

- treat `iroh-gossip` as prerelease even though it depends on stable `iroh`
- validate churn, partition recovery, and shutdown behavior for the deployment topology
- do not depend on community bootstrap trackers as the only discovery path
- treat published scale claims as unverified until reproduced in the target environment
