use std::{sync::{Arc, RwLock}, time::Duration};

use eyre::Result;
use futures_util::StreamExt;
use serde::Deserialize;
use tracing::{info, warn};

#[derive(Debug, Clone)]
pub struct CexQuote {
    pub bid: f64,
    pub ask: f64,
    pub ts_ms: u64,
}

impl CexQuote {
    pub fn mid(&self) -> f64 {
        (self.bid + self.ask) / 2.0
    }

    pub fn age_ms(&self) -> u64 {
        utils::current_time_ms().saturating_sub(self.ts_ms)
    }
}

pub type SharedCexQuote = Arc<RwLock<Option<CexQuote>>>;

#[derive(Debug, Deserialize)]
struct BookTicker {
    #[serde(rename = "b")]
    bid: String,
    #[serde(rename = "a")]
    ask: String,
}

pub fn new_shared_quote() -> SharedCexQuote {
    Arc::new(RwLock::new(None))
}

/// Keep a best-bid/best-ask reference price from Binance Spot.
/// This is intentionally read-only and does not require API keys.
pub async fn run_binance_book_ticker(shared: SharedCexQuote, symbol: &str) -> Result<()> {
    let symbol = symbol.to_ascii_lowercase();
    let url = format!("wss://stream.binance.com:9443/ws/{symbol}@bookTicker");

    loop {
        info!(%url, "connecting Binance bookTicker");
        match tokio_tungstenite::connect_async(&url).await {
            Ok((stream, _)) => {
                let (_, mut read) = stream.split();
                while let Some(msg) = read.next().await {
                    let msg = match msg {
                        Ok(msg) => msg,
                        Err(error) => {
                            warn!(?error, "Binance websocket read failed");
                            break;
                        }
                    };
                    if !msg.is_text() {
                        continue;
                    }

                    let ticker: BookTicker = match serde_json::from_str(msg.to_text()?) {
                        Ok(v) => v,
                        Err(error) => {
                            warn!(?error, "invalid Binance bookTicker payload");
                            continue;
                        }
                    };
                    let (Ok(bid), Ok(ask)) = (ticker.bid.parse::<f64>(), ticker.ask.parse::<f64>()) else {
                        continue;
                    };
                    if !(bid.is_finite() && ask.is_finite() && bid > 0.0 && ask >= bid) {
                        continue;
                    }

                    *shared.write().unwrap() = Some(CexQuote {
                        bid,
                        ask,
                        ts_ms: utils::current_time_ms(),
                    });
                }
            }
            Err(error) => warn!(?error, "Binance websocket connect failed"),
        }

        tokio::time::sleep(Duration::from_secs(1)).await;
    }
}
