# export_lib07_csv.py
import os
import re
import unicodedata
import pandas as pd

URL = "https://www.imn.ac.cr/especial/tablas/lib07.html"
OUT_DIR = "salida_csv"


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
            print(f"[Tabla {i}] originales: {list(df.columns)}")
            print(f"[Tabla {i}] normalizadas: {list(dfn.columns)}")

        if {"fecha", "temp", "lluvia", "radmax", "presmb"}.issubset(cols):
            horarios = clean_numeric_columns(dfn, non_numeric=("fecha",))
        elif {"fecha", "vmax", "sumlluv", "lluvayer", "tmax", "tmin"}.issubset(cols):
            actuales_resumen = clean_numeric_columns(dfn, non_numeric=("fecha",))
        elif {"fecha", "temp", "td", "hr", "velocidad", "direccion", "vpmax", "stavg"}.issubset(cols):
            actuales_inst = clean_numeric_columns(dfn, non_numeric=("fecha",))

    return horarios, actuales_resumen, actuales_inst


def export_outputs(debug=False):
    os.makedirs(OUT_DIR, exist_ok=True)

    tables = pd.read_html(URL, flavor="lxml", decimal=",", thousands=".")
    if not tables:
        raise ValueError("No se encontraron tablas en la URL.")

    horarios, actuales_resumen, actuales_inst = detect_tables(tables, debug=debug)

    if horarios is None and actuales_resumen is None and actuales_inst is None:
        raise ValueError("No se detectaron tablas objetivo.")

    # CSV con separador ';' y números formato LATAM
    if horarios is not None and not horarios.empty:
        to_latam_text_df(horarios, non_numeric=("fecha",), dec=2).to_csv(
            os.path.join(OUT_DIR, "lib07_horarios.csv"),
            index=False, encoding="utf-8-sig", sep=";"
        )

    if actuales_resumen is not None and not actuales_resumen.empty:
        to_latam_text_df(actuales_resumen, non_numeric=("fecha",), dec=2).to_csv(
            os.path.join(OUT_DIR, "lib07_actuales_resumen.csv"),
            index=False, encoding="utf-8-sig", sep=";"
        )

    if actuales_inst is not None and not actuales_inst.empty:
        to_latam_text_df(actuales_inst, non_numeric=("fecha",), dec=2).to_csv(
            os.path.join(OUT_DIR, "lib07_actuales_instantanea.csv"),
            index=False, encoding="utf-8-sig", sep=";"
        )

    # Excel con 3 hojas
    xlsx_path = os.path.join(OUT_DIR, "lib07_tablas.xlsx")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        if horarios is not None and not horarios.empty:
            to_latam_text_df(horarios, non_numeric=("fecha",), dec=2).to_excel(
                writer, sheet_name="Horarios", index=False
            )
        if actuales_resumen is not None and not actuales_resumen.empty:
            to_latam_text_df(actuales_resumen, non_numeric=("fecha",), dec=2).to_excel(
                writer, sheet_name="Actuales_resumen", index=False
            )
        if actuales_inst is not None and not actuales_inst.empty:
            to_latam_text_df(actuales_inst, non_numeric=("fecha",), dec=2).to_excel(
                writer, sheet_name="Actuales_inst", index=False
            )

    print(f"[OK] Exportado en carpeta: {OUT_DIR}")


if __name__ == "__main__":
    export_outputs(debug=True)