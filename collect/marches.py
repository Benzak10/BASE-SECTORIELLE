"""Cours de marché (contrats à terme) via Yahoo Finance."""
from __future__ import annotations

import pandas as pd


def collect(source_id: str, src: dict, series: list[dict]):
    import yfinance as yf

    out = []
    for s in series:
        h = yf.download(s["params"]["ticker"], period="10y", interval="1d",
                        progress=False, auto_adjust=False)
        if h.empty:
            raise RuntimeError(f"Aucune donnée pour {s['params']['ticker']}")
        close = h["Close"].squeeze().dropna()
        out.append(pd.DataFrame({"id": s["id"], "date": close.index.tz_localize(None),
                                 "valeur": close.values.astype(float)}))
    return pd.concat(out), "Yahoo Finance"
