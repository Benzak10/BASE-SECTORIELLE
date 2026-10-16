"""Base sectorielle BVC — tableau de bord Streamlit."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parent
NAVY, BLUE, GREEN, SKY = "#0E2841", "#156082", "#196B24", "#0F9ED5"
GRIS_F, GRIS_C, ROUGE = "#595959", "#BFBFBF", "#B42318"
# Ordre catégoriel fixe (validé daltonisme) — la couleur suit la série, jamais son rang
PALETTE = ["#1A6BA6", "#E97132", "#196B24", "#0F9ED5", "#A02B93"]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août",
        "sept.", "oct.", "nov.", "déc."]

st.set_page_config(page_title="Base sectorielle BVC", page_icon="📊", layout="wide")
st.markdown(f"""
<style>
  .block-container {{padding-top: 1.6rem; max-width: 1400px;}}
  h1, h2, h3 {{color: {NAVY}; letter-spacing: -0.01em;}}
  [data-testid="stSidebar"] {{background: {NAVY};}}
  [data-testid="stSidebar"] * {{color: #FFFFFF !important;}}
  [data-testid="stSidebar"] input {{color: {NAVY} !important;}}
  .kpi {{border-top: 3px solid {NAVY}; background: #F6F8FA; padding: 12px 14px 10px;
         border-radius: 4px; height: 100%;}}
  .kpi .lib {{font-size: 0.78rem; color: {GRIS_F}; text-transform: uppercase;
              letter-spacing: .03em; min-height: 2.2em;}}
  .kpi .val {{font-size: 1.55rem; font-weight: 700; color: {NAVY}; line-height: 1.2;}}
  .kpi .sub {{font-size: 0.8rem; color: {GRIS_F};}}
  .pos {{color: {GREEN}; font-weight: 600;}} .neg {{color: {ROUGE}; font-weight: 600;}}
  .tag {{display:inline-block; background:#E8EEF4; color:{NAVY}; border-radius:3px;
         padding:1px 8px; margin:0 4px 4px 0; font-size:.8rem;}}
  .src {{font-size: .78rem; color: {GRIS_F};}}
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ données
@st.cache_data(ttl=3600)
def charger():
    cat = yaml.safe_load((ROOT / "catalogue.yaml").read_text(encoding="utf-8"))
    df = pd.read_csv(ROOT / "data" / "series.csv", parse_dates=["date"])
    f = ROOT / "data" / "statut.json"
    statut = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return cat, df, statut


cat, DF, STATUT = charger()
SERIES = {s["id"]: s for s in cat["series"]}
SOURCES = cat["sources"]
SECTEURS = cat.get("secteurs", {})


def serie(i: str) -> pd.Series:
    d = DF[DF["id"] == i]
    return pd.Series(d["valeur"].values, index=d["date"]).sort_index()


def fmt(v, unite="") -> str:
    if v is None or pd.isna(v):
        return "–"
    dec = 1 if unite in ("%", "c/lb") or abs(v) < 100 else 0
    txt = f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
    return f"{txt} {unite}".strip()


def fmt_pct(v, pts=False) -> str:
    if v is None or pd.isna(v):
        return "–"
    s = f"{v:+.1f}".replace(".", ",")
    return s + (" pt" if pts else " %")


def date_lib(d, freq) -> str:
    d = pd.Timestamp(d)
    return d.strftime("%d/%m/%Y") if freq == "quotidienne" else f"{MOIS[d.month-1]} {d.year}"


def il_y_a_un_an(s: pd.Series):
    """Valeur à la même date un an plus tôt (dernière observation disponible)."""
    if s.empty:
        return None
    cible = s.index[-1] - pd.DateOffset(years=1)
    prev = s[s.index <= cible + pd.Timedelta(days=3)]
    return prev.iloc[-1] if len(prev) and prev.index[-1] >= cible - pd.Timedelta(days=10) else None


def stats(i: str) -> dict:
    meta, s = SERIES[i], serie(i)
    if s.empty:
        return {"vide": True}
    last, d = s.iloc[-1], s.index[-1]
    prev = s.iloc[-2] if len(s) > 1 else None
    a1 = il_y_a_un_an(s)
    ratio = meta.get("nature") == "ratio"
    out = {"vide": False, "last": last, "date": d,
           "var_p": (last - prev) if ratio else (last / prev - 1) * 100 if prev else None,
           "ga": (last - a1) if ratio else (last / a1 - 1) * 100 if a1 else None}
    if meta.get("nature") == "flux":  # cumul depuis janvier vs même période N-1
        cum = s[s.index.year == d.year].sum()
        cum1 = s[(s.index.year == d.year - 1) & (s.index.month <= d.month)].sum()
        out.update(cumul=cum, ga_cumul=(cum / cum1 - 1) * 100 if cum1 else None)
    return out


def variation_html(v, pts=False, inverse=False) -> str:
    if v is None or pd.isna(v):
        return "–"
    cls = "pos" if (v >= 0) != inverse else "neg"
    fl = "▲" if v >= 0 else "▼"
    return f'<span class="{cls}">{fl} {fmt_pct(v, pts)}</span>'


# ------------------------------------------------------------------ composants
def carte_kpi(i: str):
    m, k = SERIES[i], stats(i)
    if k["vide"]:
        st.markdown(f'<div class="kpi"><div class="lib">{m["nom"]}</div>'
                    f'<div class="val">–</div><div class="sub">En attente de données</div></div>',
                    unsafe_allow_html=True)
        return
    pts = m.get("nature") == "ratio"
    if m.get("nature") == "flux":
        sub = (f'Cumul {date_lib(k["date"], "m").split()[0]} : {fmt(k["cumul"], m["unite"])} '
               f'· {variation_html(k["ga_cumul"])} en cumul')
    else:
        sub = f'{variation_html(k["ga"], pts, m.get("sens") == "inverse")} sur un an'
    st.markdown(
        f'<div class="kpi"><div class="lib">{m["nom"]}</div>'
        f'<div class="val">{fmt(k["last"], m["unite"])}</div>'
        f'<div class="sub">{sub}</div>'
        f'<div class="src">{date_lib(k["date"], m["frequence"])}</div></div>',
        unsafe_allow_html=True)


def transformer(s: pd.Series, mode: str, nature: str, freq: str) -> pd.Series:
    if mode == "Glissement annuel (%)":
        if freq == "mensuelle":
            return (s.diff(12) if nature == "ratio" else s.pct_change(12, fill_method=None) * 100)
        a1 = s.reindex(s.index - pd.DateOffset(years=1), method="nearest", tolerance=pd.Timedelta(days=7))
        return pd.Series((s.values / a1.values - 1) * 100, index=s.index)
    if mode == "Base 100":
        return s / s.iloc[0] * 100
    if mode == "Cumul 12 mois glissants" and freq == "mensuelle" and nature == "flux":
        return s.rolling(12).sum()
    return s


def graphique(ids: list[str], mode: str, debut):
    fig = go.Figure()
    unites = set()
    for i in ids:
        m = SERIES[i]
        s = serie(i)
        s = transformer(s, mode, m.get("nature", ""), m["frequence"])
        s = s[s.index >= debut].dropna()
        if s.empty:
            continue
        if mode == "Base 100":
            s = s / s.iloc[0] * 100
        unites.add("" if mode != "Niveau" else m["unite"])
        meme = [j for j in SERIES if SERIES[j]["secteur"] == m["secteur"]]
        coul = PALETTE[meme.index(i) % len(PALETTE)]
        fig.add_trace(go.Scatter(
            x=s.index, y=s.values, name=m["nom"], mode="lines",
            line=dict(color=coul, width=2),
            hovertemplate="%{y:,.1f}<extra>" + m["nom"] + "</extra>"))
    titre_y = {"Glissement annuel (%)": "%", "Base 100": "Base 100"}.get(mode, " / ".join(u for u in unites if u))
    fig.update_layout(
        height=430, margin=dict(l=10, r=10, t=10, b=10), hovermode="x unified",
        plot_bgcolor="white", paper_bgcolor="white", separators=", ",
        font=dict(family="Arial", size=12, color=GRIS_F),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, title=None),
        yaxis=dict(title=titre_y, gridcolor="#EEEEEE", tickformat=",.0f" if mode == "Niveau" else ",.1f", zeroline=mode == "Glissement annuel (%)",
                   zerolinecolor=GRIS_C),
        xaxis=dict(gridcolor="#F4F4F4", tickformat="%m/%Y", hoverformat="%d/%m/%Y", showspikes=True, spikecolor=GRIS_C, spikethickness=1))
    if len(unites) > 1:
        st.caption("⚠️ Séries d'unités différentes : passez en « Base 100 » ou « Glissement annuel » pour les comparer.")
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "locale": "fr"})


def tableau_synthese(ids: list[str]) -> pd.DataFrame:
    lignes = []
    for i in ids:
        m, k = SERIES[i], stats(i)
        s = serie(i)
        pts = m.get("nature") == "ratio"
        lignes.append({
            "Secteur": m["secteur"], "Indicateur": m["nom"], "Unité": m["unite"],
            "Dernier point": date_lib(k["date"], m["frequence"]) if not k["vide"] else "–",
            "Valeur": "–" if k["vide"] else fmt(k["last"]),
            "Var. période": None if k["vide"] else k["var_p"],
            "Gliss. annuel": None if k["vide"] else k["ga"],
            "Tendance 24 m": s.tail(24 if m["frequence"] != "quotidienne" else 500).tolist(),
            "Source": SOURCES.get(m["source"], {}).get("nom", "Calcul").split(" — ")[0],
            "_pts": pts,
        })
    return pd.DataFrame(lignes)


def afficher_synthese(ids: list[str]):
    t = tableau_synthese(ids)
    st.dataframe(
        t.drop(columns="_pts"), hide_index=True, use_container_width=True,
        column_config={
            "Var. période": st.column_config.NumberColumn("Var. période (%)", format="%+.1f"),
            "Gliss. annuel": st.column_config.NumberColumn("Gliss. annuel (%)", format="%+.1f",
                                                           help="Pour les ratios : variation en points"),
            "Tendance 24 m": st.column_config.LineChartColumn("Tendance", width="small"),
        })


def export_excel(ids: list[str]) -> bytes:
    larg = (DF[DF["id"].isin(ids)].pivot(index="date", columns="id", values="valeur")
            .rename(columns={i: f'{SERIES[i]["nom"]} ({SERIES[i]["unite"]})' for i in ids})
            .sort_index(ascending=False))
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        larg.to_excel(w, sheet_name="Données")
        pd.DataFrame([{**{k: SERIES[i][k] for k in ("id", "nom", "secteur", "unite", "frequence")},
                       "source": SOURCES.get(SERIES[i]["source"], {}).get("nom", "Calcul")} for i in ids]
                     ).to_excel(w, sheet_name="Catalogue", index=False)
    return buf.getvalue()


def table_historique(ids: list[str], n: int = 13):
    larg = DF[DF["id"].isin(ids)].pivot(index="date", columns="id", values="valeur").sort_index()
    freqs = {SERIES[i]["frequence"] for i in ids}
    if "quotidienne" in freqs:
        larg = larg.resample("ME").last()
    larg = larg.tail(n).sort_index(ascending=False)
    larg.index = [date_lib(d, "mensuelle") for d in larg.index]
    larg.columns = [f'{SERIES[c]["nom"]} ({SERIES[c]["unite"]})' for c in larg.columns]
    st.dataframe(larg.style.format(lambda v: fmt(v), na_rep="–"), use_container_width=True)


# ------------------------------------------------------------------ navigation
with st.sidebar:
    st.markdown("## Base sectorielle BVC")
    st.caption("Indicateurs sectoriels des sociétés cotées à la Bourse de Casablanca")
    q = st.text_input("🔎 Rechercher", placeholder="crédit, MRE, Cosumar, tourisme…")
    pages = ["Vue d'ensemble", *SECTEURS.keys(), "Sources et mises à jour"]
    page = st.radio("Navigation", pages, label_visibility="collapsed")
    dates = [v.get("verifie") for v in STATUT.values() if v.get("verifie")]
    if dates:
        st.caption(f"Dernière vérification : {max(dates)}")


def correspond(i: str, q: str) -> bool:
    m = SERIES[i]
    txt = " ".join([m["nom"], m["secteur"], " ".join(SECTEURS.get(m["secteur"], [])),
                    SOURCES.get(m["source"], {}).get("nom", "")]).lower()
    return all(mot in txt for mot in q.lower().split())


# ------------------------------------------------------------------ pages
if q:
    ids = [i for i in SERIES if correspond(i, q)]
    st.title(f"Résultats pour « {q} »")
    st.caption(f"{len(ids)} indicateur(s)")
    if ids:
        afficher_synthese(ids)
        choix = st.multiselect("Indicateurs à tracer", ids, default=ids[:3],
                               format_func=lambda i: SERIES[i]["nom"])
        if choix:
            graphique(choix, "Niveau" if len({SERIES[i]["unite"] for i in choix}) == 1 else "Base 100",
                      pd.Timestamp.today() - pd.DateOffset(years=5))

elif page == "Vue d'ensemble":
    st.title("Vue d'ensemble")
    st.caption("Dernier point, variation et tendance de chaque indicateur suivi.")
    cles = [i for i, m in SERIES.items() if m.get("cle")]
    for ligne in range(0, len(cles), 4):
        cols = st.columns(4)
        for c, i in zip(cols, cles[ligne:ligne + 4]):
            with c:
                carte_kpi(i)
        st.write("")
    st.subheader("Tous les indicateurs")
    afficher_synthese(list(SERIES))

elif page == "Sources et mises à jour":
    st.title("Sources et mises à jour")
    lignes = []
    for sid, src in SOURCES.items():
        stt = STATUT.get(sid, {})
        etat = "✅ OK" if stt.get("ok") else ("❌ Échec" if stt else "⏳ Jamais collectée")
        if stt.get("ok") and "fichier manuel" in str(stt.get("origine", "")):
            etat = "⚠️ Fichier manuel"
        lignes.append({"Source": src["nom"], "État": etat,
                       "Dernier point": stt.get("dernier_point", "–"),
                       "Dernière vérification": stt.get("verifie", "–"),
                       "Origine": stt.get("origine", "–"),
                       "Erreur": stt.get("erreur") or "",
                       "Page": src.get("page", "")})
    st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True,
                 column_config={"Page": st.column_config.LinkColumn("Page source", display_text="ouvrir")})
    st.caption("Une source en échec conserve ses dernières données ; l'erreur est indiquée ci-dessus.")

else:
    secteur = page
    ids = [i for i, m in SERIES.items() if m["secteur"] == secteur]
    st.title(secteur)
    if SECTEURS.get(secteur):
        st.markdown("".join(f'<span class="tag">{s}</span>' for s in SECTEURS[secteur]),
                    unsafe_allow_html=True)
    cles = [i for i in ids if SERIES[i].get("cle")]
    cols = st.columns(max(len(cles), 3))
    for c, i in zip(cols, cles):
        with c:
            carte_kpi(i)
    st.write("")

    st.subheader("Graphique")
    c1, c2, c3 = st.columns([3, 1.3, 1.3])
    defaut = cles[:1] or ids[:1]
    choix = c1.multiselect("Indicateurs", ids, default=defaut, format_func=lambda i: SERIES[i]["nom"])
    modes = ["Niveau", "Glissement annuel (%)", "Base 100"]
    if any(SERIES[i].get("nature") == "flux" for i in choix):
        modes.append("Cumul 12 mois glissants")
    mode = c2.selectbox("Affichage", modes)
    horizon = c3.selectbox("Période", ["1 an", "3 ans", "5 ans", "10 ans", "Tout"], index=2)
    debut = pd.Timestamp("1900-01-01") if horizon == "Tout" else \
        pd.Timestamp.today() - pd.DateOffset(years=int(horizon.split()[0]))
    if choix:
        graphique(choix, mode, debut)

        st.subheader("Historique récent")
        table_historique(choix)
        st.download_button("⬇️ Télécharger en Excel (historique complet)", export_excel(choix),
                           file_name=f"base_sectorielle_{secteur.lower()}.xlsx")

    st.subheader(f"Indicateurs du secteur {secteur}")
    afficher_synthese(ids)
    srcs = {SERIES[i]["source"] for i in ids} - {"calcul"}
    st.markdown('<div class="src">Sources : ' + " ; ".join(SOURCES[s]["nom"] for s in srcs) + "</div>",
                unsafe_allow_html=True)
