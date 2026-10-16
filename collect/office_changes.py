"""Office des Changes — tableaux « années en lignes × mois en colonnes »."""
from __future__ import annotations

import openpyxl
import pandas as pd

from .common import get_file, norm

MOIS = ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
        "aout", "septembre", "octobre", "novembre", "decembre"]


def parse(fichier, serie_id: str) -> pd.DataFrame:
    ws = openpyxl.load_workbook(fichier, data_only=True, read_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]

    # En-tête : ligne contenant « Janvier »
    h = next(i for i, r in enumerate(rows) if any(norm(v or "") == "janvier" for v in r))
    col = {}
    for j, v in enumerate(rows[h]):
        if v and norm(v) in MOIS:
            col[MOIS.index(norm(v)) + 1] = j
    ycol = min(col.values()) - 1  # l'année est juste à gauche de « Janvier »

    corps = [r for r in rows[h + 1:] if any(isinstance(r[j], (int, float)) for j in col.values())]
    annees = [r[ycol] if isinstance(r[ycol], (int, float)) else None for r in corps]
    # Année parfois vide sur la 1re ligne (année en cours) : on la déduit de la suivante
    for k in range(len(annees) - 1, -1, -1):
        if annees[k] is None and k + 1 < len(annees) and annees[k + 1]:
            annees[k] = annees[k + 1] + 1

    out = []
    for r, an in zip(corps, annees):
        if not an:
            continue
        for m, j in col.items():
            v = r[j]
            if isinstance(v, (int, float)):
                d = pd.Timestamp(int(an), m, 1).to_period("M").to_timestamp("M")
                out.append((serie_id, d, float(v)))
    return pd.DataFrame(out, columns=["id", "date", "valeur"]).sort_values("date")


def collect(source_id: str, src: dict, series: list[dict]):
    fichier, origine = get_file(source_id, src)
    return pd.concat([parse(fichier, s["id"]) for s in series]), origine
