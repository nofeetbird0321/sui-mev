use std::{fs::{File, OpenOptions}, io::Write, path::Path, sync::Mutex};

use eyre::Result;
use serde::Serialize;

use crate::{arb::ArbResult, cex::CexQuote};

pub struct PaperLogger {
    file: Mutex<File>,
}

#[derive(Serialize)]
struct PaperRecord<'a> {
    ts_ms: u64,
    trigger_tx: String,
    source: String,
    coin_type: &'a str,
    pool_id: Option<String>,
    detection_ms: u128,
    amount_in_mist: u64,
    profit_mist: u64,
    route: String,
    cex_bid: Option<f64>,
    cex_ask: Option<f64>,
    cex_mid: Option<f64>,
    cex_quote_age_ms: Option<u64>,
}

impl PaperLogger {
    pub fn new(path: impl AsRef<Path>) -> Result<Self> {
        if let Some(parent) = path.as_ref().parent() {
            if !parent.as_os_str().is_empty() {
                std::fs::create_dir_all(parent)?;
            }
        }
        let file = OpenOptions::new().create(true).append(true).open(path)?;
        Ok(Self { file: Mutex::new(file) })
    }

    pub fn record(
        &self,
        trigger_tx: &str,
        coin_type: &str,
        pool_id: Option<String>,
        arb_result: &ArbResult,
        detection_ms: u128,
        cex_quote: Option<CexQuote>,
    ) -> Result<()> {
        let best = &arb_result.best_trial_result;
        let record = PaperRecord {
            ts_ms: utils::current_time_ms(),
            trigger_tx: trigger_tx.to_string(),
            source: arb_result.source.to_string(),
            coin_type,
            pool_id,
            detection_ms,
            amount_in_mist: best.amount_in,
            profit_mist: best.profit,
            route: format!("{:?}", best.trade_path),
            cex_bid: cex_quote.as_ref().map(|q| q.bid),
            cex_ask: cex_quote.as_ref().map(|q| q.ask),
            cex_mid: cex_quote.as_ref().map(CexQuote::mid),
            cex_quote_age_ms: cex_quote.as_ref().map(CexQuote::age_ms),
        };

        let mut file = self.file.lock().unwrap();
        serde_json::to_writer(&mut *file, &record)?;
        file.write_all(b"\n")?;
        file.flush()?;
        Ok(())
    }
}
