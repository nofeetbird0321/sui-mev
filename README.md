# Sui MEV Bot


## Run 
Start the bot with your private key.

```bash
cargo run -r --bin arb start-bot -- --private-key {}
```

## Supports

- BlueMove
- FlowX
- Aftermath
- Cetus 
- Kriya
- Abex
- Navi
- Turbos
- Deepbook
- Shio

## Relay
If you have a validator, you can let the validator push mempool transactions to your relay, which then send to the bot.

```bash
cargo run -r --bin relay
```

## Paper mode + CEX reference feed

This branch adds a safe observation mode for measuring live arbitrage opportunities before risking capital.

```bash
cargo run -r --bin arb start-bot -- \
  --private-key "$SUI_PRIVATE_KEY" \
  --paper-only true \
  --cex-symbol suiusdt \
  --paper-log data/paper-arb.jsonl \
  --use-db-simulator
```

Paper mode is **enabled by default**. Profitable simulated opportunities are appended as JSONL and are **not submitted on-chain**.

Each record includes:

- trigger transaction and source
- coin / pool
- simulated amount and net SUI profit
- selected route
- detection latency
- Binance best bid / ask / mid and quote age

Set `--paper-only false` only after validating the opportunity distribution and execution assumptions.

### Suggested validation

Run paper mode for several days and analyze:

1. opportunities/hour
2. median and p95 simulated profit
3. profit after realistic priority gas / bid assumptions
4. detection latency and stale-quote rate
5. concentration by DEX, pool, coin and route

The current code still contains the legacy DeepBook V2 adapter; migrating that adapter to DeepBook V3 should be treated as a separate compatibility change and validated against current mainnet package IDs and pool/account semantics.
