"""Bank Al-Maghrib — fichiers « séries » : libellés en colonne A, dates en ligne d'en-tête."""
from __future__ import annotations

import datetime as dt

import openpyxl
import pandas as pd

from .common import get_file, norm


def parse(fichier, series: list[dict]) -> pd.DataFrame:
    ws = openpyxl.load_workbook(fichier, data_only=True, read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))

    # Ligne d'en-tête = première ligne contenant au moins 3 dates
    head_i = next(i for i, r in enumerate(rows)
                  if sum(isinstance(v, (dt.date, dt.datetime)) for v in r) >= 3)
    dates = rows[head_i]

    out = []
    for s in series:
        cle = norm(s["params"]["ligne"])
        row = next((r for r in rows[head_i + 1:]
                    if r and r[0] and norm(r[0]).startswith(cle)), None)
        if row is None:
            raise RuntimeError(f"Ligne « {s['params']['ligne']} » absente du fichier BKAM")
        for d, v in zip(dates[1:], row[1:]):
            if isinstance(d, (dt.date, dt.datetime)) and isinstance(v, (int, float)):
                # BKAM date certains mois au 25 : on normalise en fin de mois
                fin_mois = pd.Timestamp(d).to_period("M").to_timestamp("M")
                out.append((s["id"], fin_mois, float(v)))
    return pd.DataFrame(out, columns=["id", "date", "valeur"])


def collect(source_id: str, src: dict, series: list[dict]):
    fichier, origine = get_file(source_id, src)
    return parse(fichier, series), origine
