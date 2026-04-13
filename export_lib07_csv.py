# export_lib07_csv.py
import os
import re
import unicodedata
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Optional, Union

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


def floor_to_quarter(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)


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


def append_latam_csv(df: pd.DataFrame, path: str, non_numeric=("fecha",), dec=2):
    """
    Append robusto en CSV histórico:
    - Si no existe: crea.
    - Si existe con esquema distinto: backup + reinicio limpio.
    """
    out = to_latam_text_df(df, non_numeric=non_numeric, dec=dec)
    p = Path(path)

    if not p.exists():
        out.to_csv(path, mode="w", header=True, index=False, sep=";", encoding="utf-8-sig")
        return

    # Comparar esquema
    try:
        existing_cols = pd.read_csv(path, sep=";", nrows=0, encoding="utf-8-sig").columns.tolist()
    except Exception:
        existing_cols = pd.read_csv(path, sep=";", nrows=0, encoding="utf-8").columns.tolist()

    new_cols = out.columns.tolist()

    if existing_cols != new_cols:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_path = str(p).replace(".csv", f"_schema_backup_{ts}.csv")
        os.replace(path, backup_path)
        out.to_csv(path, mode="w", header=True, index=False, sep=";", encoding="utf-8-sig")
    else:
        out.to_csv(path, mode="a", header=False, index=False, sep=";", encoding="utf-8")


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

    # Si no se detectó ninguna tabla conocida, loguear columnas para diagnóstico
    if horarios is None and actuales_resumen is None and actuales_inst is None:
        print("[WARN] No se detectaron tablas objetivo. Columnas encontradas:")
        for i, df in enumerate(tables, 1):
            dfn = normalize_columns(df)
            print(f"  Tabla {i}: {list(dfn.columns)}")

    return horarios, actuales_resumen, actuales_inst


def _resolve_forced_slot(forced_slot: Optional[Union[str, datetime]]) -> datetime:
    if forced_slot is None:
        return floor_to_quarter(datetime.now(timezone.utc))

    if isinstance(forced_slot, datetime):
        return forced_slot.astimezone(timezone.utc).replace(second=0, microsecond=0)

    # string esperado: "YYYY-MM-DD HH:MM:SS"
    dt = datetime.strptime(str(forced_slot), "%Y-%m-%d %H:%M:%S")
    return dt.replace(tzinfo=timezone.utc, second=0, microsecond=0)


def export_outputs(debug=False, forced_slot: Optional[Union[str, datetime]] = None):
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(HIST_DIR, exist_ok=True)

    # Fetch con timeout explícito para no bloquear el runner
    resp = requests.get(URL, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text), flavor="lxml", decimal=",", thousands=".")

    if not tables:
        raise ValueError("No se encontraron tablas en la URL.")

    horarios, actuales_resumen, actuales_inst = detect_tables(tables, debug=debug)
    if horarios is None and actuales_resumen is None and actuales_inst is None:
        raise ValueError("No se detectaron tablas objetivo.")

    now_utc = datetime.now(timezone.utc)
    captura_utc_real = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    slot_dt = _resolve_forced_slot(forced_slot)
    programado_slot = slot_dt.strftime("%Y-%m-%d %H:%M:%S")

    # ---------- Estado actual ----------
    if horarios is not None and not horarios.empty:
        to_latam_text_df(horarios, non_numeric=("fecha",), dec=2).to_csv(
            os.path.join(OUT_DIR, "lib07_horarios.csv"),
            index=False, sep=";", encoding="utf-8-sig"
        )

    if actuales_resumen is not None and not actuales_resumen.empty:
        to_latam_text_df(actuales_resumen, non_numeric=("fecha",), dec=2).to_csv(
            os.path.join(OUT_DIR, "lib07_actuales_resumen.csv"),
            index=False, sep=";", encoding="utf-8-sig"
        )

    if actuales_inst is not None and not actuales_inst.empty:
        to_latam_text_df(actuales_inst, non_numeric=("fecha",), dec=2).to_csv(
            os.path.join(OUT_DIR, "lib07_actuales_instantanea.csv"),
            index=False, sep=";", encoding="utf-8-sig"
        )

    with pd.ExcelWriter(os.path.join(OUT_DIR, "lib07_tablas.xlsx"), engine="openpyxl") as writer:
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

    # ---------- Histórico acumulado (1 fila por corrida) ----------
    if horarios is not None and not horarios.empty:
        h1 = horarios.iloc[[0]].copy()
        h1.insert(0, "programado_slot", programado_slot)
        h1.insert(1, "captura_utc_real", captura_utc_real)
        append_latam_csv(
            h1,
            os.path.join(HIST_DIR, "lib07_horarios_historico.csv"),
            non_numeric=("programado_slot", "captura_utc_real", "fecha"),
            dec=2
        )

    if actuales_resumen is not None and not actuales_resumen.empty:
        ar1 = actuales_resumen.iloc[[0]].copy()
        ar1.insert(0, "programado_slot", programado_slot)
        ar1.insert(1, "captura_utc_real", captura_utc_real)
        append_latam_csv(
            ar1,
            os.path.join(HIST_DIR, "lib07_actuales_resumen_historico.csv"),
            non_numeric=("programado_slot", "captura_utc_real", "fecha"),
            dec=2
        )

    if actuales_inst is not None and not actuales_inst.empty:
        ai1 = actuales_inst.iloc[[0]].copy()
        ai1.insert(0, "programado_slot", programado_slot)
        ai1.insert(1, "captura_utc_real", captura_utc_real)
        append_latam_csv(
            ai1,
            os.path.join(HIST_DIR, "lib07_actuales_instantanea_historico.csv"),
            non_numeric=("programado_slot", "captura_utc_real", "fecha"),
            dec=2
        )

    print(f"[OK] Exportación completa | slot={programado_slot} | real={captura_utc_real}")


if __name__ == "__main__":
    export_outputs(debug=True)