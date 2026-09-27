# [iroh][iroh:docs]

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

## refs

[iroh:docs]: https://docs.rs/iroh/latest/iroh/
    `read_to_end` terminates once the client calls `finish` on its send stream

[iroh:endpoint]: https://docs.rs/iroh/latest/iroh/endpoint/struct.Endpoint.html
    It is recommended to only create a single instance per application

[iroh:presets]: https://docs.rs/iroh/latest/iroh/endpoint/presets/index.html
