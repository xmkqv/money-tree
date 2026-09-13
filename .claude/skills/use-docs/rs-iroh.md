# iroh

## endpoint

```rs
use iroh::{Endpoint, endpoint::presets};
endpoint = Endpoint::builder(presets::N0)
    .alpns(vec![alpn.to_vec()])
    .bind().await?
```

## outgoing exchange

```rs
connection = endpoint.connect(address, alpn).await?
(send, recv) = connection.open_bi().await?
send.write_all(payload).await?
send.finish()?
response = recv.read_to_end(max_bytes).await?
```

## incoming exchange

```rs
incoming = endpoint.accept().await?
connection = incoming.await?
(send, recv) = connection.accept_bi().await?
request = recv.read_to_end(max_bytes).await?
send.write_all(response).await?
send.finish()?
```

## shutdown

```rs
connection.close(0u8.into(), b"complete")
endpoint.close().await
```

## tips

- endpoint addresses combine endpoint identity with transport addresses.
- peers agree on the alpn before establishing a connection.
- a stream becomes visible to its peer after the initiator sends data.
- finishing the send side allows the peer's `read_to_end` to complete.
- [presets][presets] configure discovery and relay behavior.
- [connections][endpoint] share the endpoint's underlying connectivity.

## refs

[endpoint]: https://docs.rs/iroh/latest/iroh/endpoint/struct.Endpoint.html
[presets]: https://docs.rs/iroh/latest/iroh/endpoint/presets/index.html
