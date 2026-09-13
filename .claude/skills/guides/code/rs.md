# rs

## form

- rs:form:code`*`

## types

### constrained value

```rs
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct ShelfKey(String);
#[derive(Debug, Eq, PartialEq, thiserror::Error)]
#[error("shelf key must not be blank")]
pub struct ParseShelfKeyError;

impl std::str::FromStr for ShelfKey {
    type Err = ParseShelfKeyError;

    fn from_str(text: &str) -> Result<Self, ParseShelfKeyError> {
        let value = text.trim();
        (!value.is_empty())
            .then(|| Self(value.to_owned()))
            .ok_or(ParseShelfKeyError)
    }
}
```

### closed mode

```rs
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum LoanMode {
    Standard,
    Short,
}
pub fn loan_days(mode: LoanMode) -> u8 {
    match mode {
        LoanMode::Standard => 21,
        LoanMode::Short => 7,
    }
}
```

### capability

```rs
pub trait Clock {
    fn now(&self) -> std::time::Instant;
}
```

## state

### owned actor

```rs
#[derive(Clone)]
pub struct Loans(tokio::sync::mpsc::Sender<LoanMessage>);

impl Loans {
    pub async fn renew(&self, id: BookId) -> Result<(), SendLoanMessageError> {
        self.0.send(LoanMessage::Renew(id)).await.map_err(|_| SendLoanMessageError)
    }
}

async fn serve_loans(mut inbox: tokio::sync::mpsc::Receiver<LoanMessage>) {
    let mut open = std::collections::HashSet::new();
    while let Some(message) = inbox.recv().await {
        handle(message, &mut open);
    }
}
```

### replied request

```rs
pub enum LoanMessage {
    Renew(BookId),
    Due(BookId, tokio::sync::oneshot::Sender<Option<Date>>),
}

impl Loans {
    pub async fn due(&self, id: BookId) -> Result<Option<Date>, SendLoanMessageError> {
        let (reply, response) = tokio::sync::oneshot::channel();
        self.0.send(LoanMessage::Due(id, reply)).await.map_err(|_| SendLoanMessageError)?;
        response.await.map_err(|_| SendLoanMessageError)
    }
}
```

### snapshot state

```rs
pub struct Settings(arc_swap::ArcSwap<Config>);

impl Settings {
    pub fn current(&self) -> std::sync::Arc<Config> {
        self.0.load_full()
    }

    pub fn replace(&self, config: Config) {
        self.0.store(std::sync::Arc::new(config));
    }
}
```

### lagged fanout

```rs
async fn follow(mut events: tokio::sync::broadcast::Receiver<ReturnEvent>) {
    loop {
        match events.recv().await {
            Ok(event) => apply(event),
            Err(tokio::sync::broadcast::error::RecvError::Lagged(_)) => resync().await,
            Err(tokio::sync::broadcast::error::RecvError::Closed) => break,
        }
    }
}
```

## boundaries

### portable spawn

```rs
pub fn spawn(future: impl std::future::Future<Output = ()> + 'static) {
    #[cfg(target_arch = "wasm32")]
    wasm_bindgen_futures::spawn_local(future);
    #[cfg(not(target_arch = "wasm32"))]
    tokio::task::spawn_local(future);
}
```

## fallibility

### contextual error

```rs
#[derive(Debug, thiserror::Error)]
pub enum LoadCatalogError {
    #[error("catalog {path} could not be read")]
    Read {
        path: std::path::PathBuf,
        #[source]
        source: std::io::Error,
    },
}
```

## lifecycle

### cooperative shutdown

```rs
pub async fn serve(token: tokio_util::sync::CancellationToken) {
    let tasks = tokio_util::task::TaskTracker::new();
    tasks.spawn(drain_returns(token.clone()));
    tasks.close();
    token.cancelled().await;
    tasks.wait().await;
}

async fn drain_returns(token: tokio_util::sync::CancellationToken) {
    loop {
        tokio::select! {
            _ = token.cancelled() => break,
            job = next_return() => handle(job).await,
        }
    }
    flush().await;
}
```

## verification

### behavioral test

```rs
#[test]
fn rejects_blank_shelf_key() {
    assert!(matches!(" ".parse::<ShelfKey>(), Err(ParseShelfKeyError)));
}
```
