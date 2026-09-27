# [iroh-gossip][iroh-gossip:docs]

## spawn

```rs
use iroh::protocol::Router;
use iroh_gossip::{Gossip, ALPN};

gossip = Gossip::builder()
    .max_message_size(max_bytes)
    .spawn(endpoint.clone())
router = Router::builder(endpoint)
    .accept(ALPN, gossip.clone())
    .spawn()
```

## membership

```rs
use iroh_gossip::proto::HyparviewConfig;

gossip = Gossip::builder()
    .membership_config(HyparviewConfig {
        active_view_capacity: active_peers,
        passive_view_capacity: known_peers,
        ..Default::default()
    })
    .spawn(endpoint.clone())
```

## many topics per peer

```rs
use iroh::endpoint::QuicTransportConfig;

transport = QuicTransportConfig::builder()
    .max_concurrent_uni_streams(topics_per_peer * 2)
    .build()
endpoint = Endpoint::builder(preset)
    .transport_config(transport)
    .bind().await?
```

## topic id

```rs
use iroh_gossip::TopicId;

topic_id = TopicId::from_bytes(Sha256::digest(name).into())
```

## subscribe

```rs
(sender, receiver) = gossip.subscribe(topic_id, bootstrap_ids).await?.split()
receiver.joined().await?
```

## broadcast

```rs
use bytes::Bytes;

sender.broadcast(Bytes::from(payload)).await?
```

## receive

```rs
use iroh_gossip::api::Event;
use n0_future::StreamExt;

while let Some(event) = receiver.next().await
    match event?
        Event::Received(message) → handle(message.delivered_from, message.content)
        Event::NeighborUp(id) | Event::NeighborDown(id) → track(id)
        Event::Lagged → resubscribe()
```

## resubscribe

```rs
peers: Vec<_> = receiver.neighbors().collect()
drop((sender, receiver))
(sender, receiver) = gossip.subscribe(topic_id, peers).await?.split()
```

## leave

```rs
drop((sender, receiver))
```

## bootstrap addresses

```rs
use iroh::address_lookup::memory::MemoryLookup;

lookup = MemoryLookup::new()
endpoint = Endpoint::builder(presets::N0)
    .address_lookup(lookup.clone())
    .bind().await?
lookup.add_endpoint_info(peer_addr)
```

## shutdown

```rs
router.shutdown().await?
endpoint.close().await
```

## wasm

```toml
iroh = { version = "1", default-features = false }
iroh-gossip = { version = "0.101", default-features = false }
```

## refs

[iroh-gossip:docs]: https://docs.rs/iroh-gossip/latest/iroh_gossip/

[iroh-gossip:builder]: https://docs.rs/iroh-gossip/latest/iroh_gossip/net/struct.Builder.html
    Sets the maximum message size in bytes. By default this is `4096` bytes.
    If you set a custom ALPN, you have to use the same ALPN when registering

[iroh-gossip:proto]: https://docs.rs/iroh-gossip/latest/iroh_gossip/proto/index.html
    In the default configuration, the active view has a size of 5 and the passive view a size of 30.
    joining multiple topics increases the number of open connections to peers

[iroh-gossip:hyparview-config]: https://docs.rs/iroh-gossip/latest/iroh_gossip/proto/struct.HyparviewConfig.html
    Number of peers to which active connections are maintained

[iroh-gossip:topic]: https://docs.rs/iroh-gossip/latest/iroh_gossip/api/struct.GossipTopic.html
    Once the GossipTopic is dropped, the network actor will leave the gossip topic.

[iroh-gossip:receiver]: https://docs.rs/iroh-gossip/latest/iroh_gossip/api/struct.GossipReceiver.html
    Note that this consumes this initial `NeighborUp` event.

[iroh-gossip:event]: https://docs.rs/iroh-gossip/latest/iroh_gossip/api/enum.Event.html

[iroh-gossip:message]: https://docs.rs/iroh-gossip/latest/iroh_gossip/api/struct.Message.html
    This is not the same as the original author.

[iroh-gossip:join-options]: https://docs.rs/iroh-gossip/latest/iroh_gossip/api/struct.JoinOptions.html
    If a subscriber is lagging, it should be closed and re-opened.

[iroh-gossip:api-source]: https://github.com/n0-computer/iroh-gossip/blob/main/src/api.rs
    Messages will be queued until a first connection is available.

[iroh-gossip:net-source]: https://github.com/n0-computer/iroh-gossip/blob/main/src/net.rs
    With the default settings, the protocol will maintain up to 5 peer connections per topic.
    peers: HashMap<EndpointId, PeerState> — one active connection per peer, shared by every topic
    The first endpoint will subscribe twice and connect to the second endpoint
    This leaves all topics, sending `Disconnect` messages to peers

[iroh-gossip:util-source]: https://github.com/n0-computer/iroh-gossip/blob/main/src/net/util.rs
    let mut stream = self.conn.open_uni().await?; — one uni stream per topic per connection, held open
    QUIC default max_concurrent_uni_streams is 100; past it open_uni blocks the whole gossip actor
    idle topic ≈ 41 KB per node, dominated by the 256-slot broadcast channel
    if len >= max_message_size { return Err(e!(WriteError::TooLarge)); }

[iroh-gossip:plumtree-source]: https://github.com/n0-computer/iroh-gossip/blob/main/src/proto/plumtree.rs

[iroh-gossip:chat]: https://github.com/n0-computer/iroh-gossip/blob/main/examples/chat.rs

[iroh-examples:browser-chat]: https://github.com/n0-computer/iroh-examples/blob/main/browser-chat/shared/src/lib.rs

[iroh:gossip-guide]: https://docs.iroh.computer/connecting/gossip

[iroh:wasm]: https://docs.iroh.computer/languages/wasm-browser

[iroh-gossip:changelog]: https://github.com/n0-computer/iroh-gossip/blob/main/CHANGELOG.md
    [breaking] Remove `Joined` event, use `NeighborUp`
    Keep topic alive if either senders or receivers exist

[iroh-gossip:version]: https://crates.io/crates/iroh-gossip/0.101.0
