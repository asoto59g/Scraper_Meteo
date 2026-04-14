# export_lib07_csv.py
import os
import re
import unicodedata
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

URL = "https://www.imn.ac.cr/especial/tablas/lib07.html"
OUT_DIR = "salida_csv"
HIST_DIR = os.path.join(OUT_DIR, "historico")

# Timeout de red: evita bloquear el runner indefinidamente si el IMN está lento
REQUEST_TIMEOUT = 30  # segundos


def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # quita tildes
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [norm(c) for c in out.columns]
    return out


def parse_num_latam(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if not s:
        return None
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s:
        return None
    # Formato LATAM web: 1.001,12
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def clean_numeric_columns(df: pd.DataFrame, non_numeric=("fecha",)):
    out = df.copy()
    for col in out.columns:
        if col in non_numeric:
            continue
        out[col] = out[col].apply(parse_num_latam)
    return out


def format_latam_number(x, dec=2):
    """1001.12 -> 1.001,12"""
    if pd.isna(x):
        return ""
    s = f"{float(x):,.{dec}f}"  # 1,001.12
    s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def to_latam_text_df(df: pd.DataFrame, non_numeric=("fecha",), dec=2):
    out = df.copy()
    for col in out.columns:
        if col in non_numeric:
            continue
        out[col] = out[col].apply(lambda v: format_latam_number(v, dec=dec))
    return out


def detect_horarios(tables, debug=False):
    """
    Detecta y retorna únicamente la tabla de datos horarios (ventana 24h).
    Las tablas actuales_resumen y actuales_instantanea se ignoran.
    """
    for i, df in enumerate(tables, 1):
        dfn = normalize_columns(df)
        cols = set(dfn.columns)
        if debug:
            print(f"[Tabla {i}] normalizadas: {list(dfn.columns)}")
        if {"fecha", "temp", "lluvia", "radmax", "presmb"}.issubset(cols):
            return clean_numeric_columns(dfn, non_numeric=("fecha",))

    print("[WARN] No se detectó tabla horarios. Columnas encontradas:")
    for i, df in enumerate(tables, 1):
        print(f"  Tabla {i}: {list(normalize_columns(df).columns)}")
    return None


def merge_new_rows_to_history(df: pd.DataFrame, captura_utc: str) -> int:
    """
    Compara las filas entrantes contra el CSV histórico usando 'fecha' como clave.
    Inserta SOLO las filas con 'fecha' nueva; nunca repite registros.
    Retorna el número de filas insertadas.
    """
    hist_path = Path(HIST_DIR) / "lib07_horarios_historico.csv"
    os.makedirs(HIST_DIR, exist_ok=True)

    # Leer fechas ya presentes en el histórico
    existing_fechas: set = set()
    hist_exists = hist_path.exists() and hist_path.stat().st_size > 0

    if hist_exists:
        try:
            hist = pd.read_csv(
                hist_path, sep=";", dtype=str, encoding="utf-8-sig",
                engine="python", on_bad_lines="skip"
            )
        except Exception:
            hist = pd.read_csv(
                hist_path, sep=";", dtype=str, encoding="utf-8",
                engine="python", on_bad_lines="skip"
            )
        if "fecha" in hist.columns:
            existing_fechas = set(hist["fecha"].dropna().str.strip().tolist())

    # Filtrar solo filas nuevo
    df_new = df.copy()
    df_new.insert(0, "captura_utc", captura_utc)
    fecha_key = df_new["fecha"].astype(str).str.strip()
    to_add = df_new[~fecha_key.isin(existing_fechas)]

    if to_add.empty:
        print("[HIST] Sin filas nuevas para el histórico.")
        return 0

    # Convertir a formato texto LATAM y agregar
    out = to_latam_text_df(to_add, non_numeric=("captura_utc", "fecha"), dec=2)

    if not hist_exists:
        out.to_csv(hist_path, mode="w", header=True, index=False,
                   sep=";", encoding="utf-8-sig")
    else:
        out.to_csv(hist_path, mode="a", header=False, index=False,
                   sep=";", encoding="utf-8")

    print(f"[HIST] +{len(to_add)} fila(s) nueva(s) insertada(s) al histórico.")
    return len(to_add)


def export_outputs(debug=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(HIST_DIR, exist_ok=True)

    # Fetch con timeout explícito
    resp = requests.get(URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text), flavor="lxml", decimal=",", thousands=".")

    if not tables:
        raise ValueError("No se encontraron tablas en la URL.")

    horarios = detect_horarios(tables, debug=debug)
    if horarios is None or horarios.empty:
        raise ValueError("No se detectó la tabla horarios.")

    captura_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # 1. Estado actual — ventana deslizante de 24h (se sobreescribe en cada captura)
    to_latam_text_df(horarios, non_numeric=("fecha",), dec=2).to_csv(
        os.path.join(OUT_DIR, "lib07_horarios.csv"),
        index=False, sep=";", encoding="utf-8-sig"
    )

    # 2. Histórico acumulado — agrega solo las horas nuevas que todavía no están registradas
    merge_new_rows_to_history(horarios, captura_utc)

    print(f"[OK] Exportación completa | captura_utc={captura_utc}")


if __name__ == "__main__":
    export_outputs(debug=True)