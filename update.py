"""Mise à jour de la base : lance chaque collecteur, fusionne, calcule les séries dérivées.

Usage : python update.py
Sorties : data/series.csv (format long id/date/valeur) et data/statut.json
Si une source échoue, ses anciennes données sont conservées et l'erreur est notée.
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import sys
import traceback
from collections import defaultdict
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "series.csv"
STATUT = ROOT / "data" / "statut.json"


def charger_catalogue() -> dict:
    return yaml.safe_load((ROOT / "catalogue.yaml").read_text(encoding="utf-8"))


def calculer(df: pd.DataFrame, series: list[dict]) -> pd.DataFrame:
    """Séries calculées : la formule utilise les id d'autres séries."""
    larg = df.pivot_table(index="date", columns="id", values="valeur")
    res = []
    for s in series:
        if s.get("source") != "calcul":
            continue
        v = larg.eval(s["formule"]).dropna()
        res.append(pd.DataFrame({"id": s["id"], "date": v.index, "valeur": v.values}))
    return pd.concat(res) if res else pd.DataFrame(columns=df.columns)


def main(seulement: list[str] | None = None) -> int:
    cat = charger_catalogue()
    ancien = pd.read_csv(DATA, parse_dates=["date"]) if DATA.exists() else \
        pd.DataFrame(columns=["id", "date", "valeur"])
    statut = json.loads(STATUT.read_text(encoding="utf-8")) if STATUT.exists() else {}

    par_source = defaultdict(list)
    for s in cat["series"]:
        if s["source"] != "calcul":
            par_source[s["source"]].append(s)

    blocs, maj = [], set()
    maintenant = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for sid, series in par_source.items():
        if seulement and sid not in seulement:
            continue
        src = cat["sources"][sid]
        try:
            mod = importlib.import_module(f"collect.{src['collecteur']}")
            df, origine = mod.collect(sid, src, series)
            df = df.dropna()
            blocs.append(df)
            maj.update(s["id"] for s in series)
            statut[sid] = {"ok": True, "verifie": maintenant, "origine": origine,
                           "dernier_point": str(pd.to_datetime(df["date"]).max().date()),
                           "points": int(len(df)), "erreur": None}
            print(f"OK    {sid:12s} {len(df):6d} points  -> {statut[sid]['dernier_point']}")
        except Exception as e:  # noqa: BLE001
            prev = statut.get(sid, {})
            statut[sid] = {**prev, "ok": False, "verifie": maintenant, "erreur": str(e)[:500]}
            print(f"ECHEC {sid:12s} {e}")
            traceback.print_exc()

    garde = ancien[~ancien["id"].isin(maj)]
    df = pd.concat([garde, *blocs], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    df["valeur"] = pd.to_numeric(df["valeur"], errors="coerce")
    calc_ids = [s["id"] for s in cat["series"] if s["source"] == "calcul"]
    df = df[~df["id"].isin(calc_ids)]
    df = pd.concat([df, calculer(df, cat["series"])], ignore_index=True)
    df = df.drop_duplicates(["id", "date"], keep="last").sort_values(["id", "date"])

    DATA.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DATA, index=False, date_format="%Y-%m-%d")
    STATUT.write_text(json.dumps(statut, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
