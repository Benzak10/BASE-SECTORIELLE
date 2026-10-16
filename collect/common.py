"""Outils communs : téléchargement « comme un navigateur », recherche de lien, repli manuel."""
from __future__ import annotations

import io
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
MANUEL = ROOT / "data" / "manuel"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def norm(s: str) -> str:
    """Minuscules, sans accents ni espaces superflus (pour comparer des libellés)."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _get_requests(url: str) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    if b"captcha" in r.content[:5000].lower():
        raise RuntimeError("page anti-robot")
    return r.content


def _get_playwright(url: str) -> bytes:
    """Repli : vrai navigateur Chromium (pages protégées)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(user_agent=HEADERS["User-Agent"], locale="fr-FR")
        page = ctx.new_page()
        if url.lower().split("?")[0].endswith((".xlsx", ".xls")):
            with page.expect_download() as dl:
                try:
                    page.goto(url)
                except Exception:
                    pass  # un téléchargement interrompt goto : c'est normal
            data = Path(dl.value.path()).read_bytes()
        else:
            page.goto(url, wait_until="networkidle", timeout=90_000)
            data = page.content().encode("utf-8")
        browser.close()
        return data


def fetch(url: str) -> bytes:
    try:
        return _get_requests(url)
    except Exception as e1:  # noqa: BLE001
        try:
            return _get_playwright(url)
        except Exception as e2:  # noqa: BLE001
            raise RuntimeError(f"Téléchargement impossible ({e1} / {e2})") from e2


def find_link(page_url: str, contains: str) -> str:
    """Repère sur une page le lien dont l'adresse OU le texte contient `contains`."""
    from bs4 import BeautifulSoup

    html = fetch(page_url)
    soup = BeautifulSoup(html, "html.parser")
    key = norm(contains)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if key in norm(href.replace("%20", " ")) or key in norm(a.get_text(" ")):
            return urljoin(page_url, href)
    raise RuntimeError(f"Lien « {contains} » introuvable sur {page_url}")


def get_file(source_id: str, src: dict) -> tuple[io.BytesIO, str]:
    """Télécharge le fichier d'une source ; à défaut, utilise data/manuel/<source_id>.xlsx."""
    try:
        url = find_link(src["page"], src["lien_contient"])
        return io.BytesIO(fetch(url)), url
    except Exception as e:  # noqa: BLE001
        for ext in (".xlsx", ".xls", ".XLSX"):
            f = MANUEL / f"{source_id}{ext}"
            if f.exists():
                return io.BytesIO(f.read_bytes()), f"fichier manuel ({f.name}) — téléchargement échoué : {e}"[:300]
        raise RuntimeError(str(e)) from e
