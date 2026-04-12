# export_lib07_csv.py
import os
import re
import unicodedata
from datetime import datetime, timezone
import pandas as pd

URL = "https://www.imn.ac.cr/especial/tablas/lib07.html"
OUT_DIR = "salida_csv"
HIST_DIR = os.path.join(OUT_DIR, "historico")


def norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
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


def detect_tables(tables, debug=False):
    horarios = None
    actuales_resumen = None
    actuales_inst = None

    for i, df in enumerate(tables, 1):
        dfn = normalize_columns(df)
        cols = set(dfn.columns)

        if debug:
            print(f"[Tabla {i}] {list(df.columns)} -> {list(dfn.columns)}")

        if {"fecha", "temp", "lluvia", "radmax", "presmb"}.issubset(cols):
            horarios = clean_numeric_columns(dfn, non_numeric=("fecha",))
        elif {"fecha", "vmax", "sumlluv", "lluvayer", "tmax", "tmin"}.issubset(cols):
            actuales_resumen = clean_numeric_columns(dfn, non_numeric=("fecha",))
        elif {"fecha", "temp", "td", "hr", "velocidad", "direccion", "vpmax", "stavg"}.issubset(cols):
            actuales_inst = clean_numeric_columns(dfn, non_numeric=("fecha",))

    return horarios, actuales_resumen, actuales_inst


def export_outputs(debug=False):
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(HIST_DIR, exist_ok=True)

    tables = pd.read_html(URL, flavor="lxml", decimal=",", thousands=".")
    if not tables:
        raise ValueError("No se encontraron tablas.")

    horarios, actuales_resumen, actuales_inst = detect_tables(tables, debug=debug)
    if horarios is None and actuales_resumen is None and actuales_inst is None:
        raise ValueError("No se detectaron tablas objetivo.")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    # DataFrames formateados LATAM (texto)
    h_latam = to_latam_text_df(horarios, non_numeric=("fecha",), dec=2) if horarios is not None else None
    ar_latam = to_latam_text_df(actuales_resumen, non_numeric=("fecha",), dec=2) if actuales_resumen is not None else None
    ai_latam = to_latam_text_df(actuales_inst, non_numeric=("fecha",), dec=2) if actuales_inst is not None else None

    # ---- Archivos "último estado" ----
    if h_latam is not None and not h_latam.empty:
        h_latam.to_csv(os.path.join(OUT_DIR, "lib07_horarios.csv"), index=False, sep=";", encoding="utf-8-sig")
    if ar_latam is not None and not ar_latam.empty:
        ar_latam.to_csv(os.path.join(OUT_DIR, "lib07_actuales_resumen.csv"), index=False, sep=";", encoding="utf-8-sig")
    if ai_latam is not None and not ai_latam.empty:
        ai_latam.to_csv(os.path.join(OUT_DIR, "lib07_actuales_instantanea.csv"), index=False, sep=";", encoding="utf-8-sig")

    with pd.ExcelWriter(os.path.join(OUT_DIR, "lib07_tablas.xlsx"), engine="openpyxl") as writer:
        if h_latam is not None and not h_latam.empty:
            h_latam.to_excel(writer, sheet_name="Horarios", index=False)
        if ar_latam is not None and not ar_latam.empty:
            ar_latam.to_excel(writer, sheet_name="Actuales_resumen", index=False)
        if ai_latam is not None and not ai_latam.empty:
            ai_latam.to_excel(writer, sheet_name="Actuales_inst", index=False)

    # ---- Histórico por timestamp ----
    if h_latam is not None and not h_latam.empty:
        h_latam.to_csv(os.path.join(HIST_DIR, f"lib07_horarios_{ts}.csv"), index=False, sep=";", encoding="utf-8-sig")
    if ar_latam is not None and not ar_latam.empty:
        ar_latam.to_csv(os.path.join(HIST_DIR, f"lib07_actuales_resumen_{ts}.csv"), index=False, sep=";", encoding="utf-8-sig")
    if ai_latam is not None and not ai_latam.empty:
        ai_latam.to_csv(os.path.join(HIST_DIR, f"lib07_actuales_instantanea_{ts}.csv"), index=False, sep=";", encoding="utf-8-sig")

    with pd.ExcelWriter(os.path.join(HIST_DIR, f"lib07_tablas_{ts}.xlsx"), engine="openpyxl") as writer:
        if h_latam is not None and not h_latam.empty:
            h_latam.to_excel(writer, sheet_name="Horarios", index=False)
        if ar_latam is not None and not ar_latam.empty:
            ar_latam.to_excel(writer, sheet_name="Actuales_resumen", index=False)
        if ai_latam is not None and not ai_latam.empty:
            ai_latam.to_excel(writer, sheet_name="Actuales_inst", index=False)

    print(f"[OK] Exportado. Timestamp UTC: {ts}")


if __name__ == "__main__":
    export_outputs(debug=True)