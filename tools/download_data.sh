#!/usr/bin/env bash
set -euo pipefail

# Download historical data for the configured whitelist.
# Uses freqtrade download-data with config.base.json.
freqtrade download-data \
  -c user_data/config/config.base.json \
  --timerange 20200101- \
  --timeframes 5m 15m 1h 4h \
  --trading-mode futures
