# DAT Dashboard

Live performance dashboard tracking Digital Asset Treasury (DAT) companies against crypto benchmarks.

## Running locally

```bash
uv run streamlit run app.py
```

## Adding new ecosystems

Add a JSON config to `configs/` (see `configs/solana.json` for the format). The dashboard auto-discovers all config files.
