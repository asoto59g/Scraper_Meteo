# dedupe_history.py
from pathlib import Path
import pandas as pd

HIST_DIR = Path("salida_csv/historico")


def read_csv_robust(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig", engine="python", on_bad_lines="skip")
    except Exception:
        return pd.read_csv(path, sep=";", dtype=str, encoding="utf-8", engine="python", on_bad_lines="skip")


def dedupe_file(path: Path) -> int:
    df = read_csv_robust(path)
    if df.empty:
        return 0

    if "programado_slot" not in df.columns or "captura_utc_real" not in df.columns:
        print(f"[SKIP] {path.name}: faltan columnas programado_slot/captura_utc_real")
        return 0

    before = len(df)

    df["_slot_dt"] = pd.to_datetime(df["programado_slot"], errors="coerce", utc=True)
    df["_real_dt"] = pd.to_datetime(df["captura_utc_real"], errors="coerce", utc=True)

    # estricto: por slot + fecha (si existe)
    subset_keys = ["programado_slot", "fecha"] if "fecha" in df.columns else ["programado_slot"]

    df = df.sort_values(by=["_slot_dt", "_real_dt"], ascending=[True, True])
    df = df.drop_duplicates(subset=subset_keys, keep="last")
    df = df.sort_values(by=["_slot_dt"], ascending=True)
    df = df.drop(columns=["_slot_dt", "_real_dt"])

    removed = before - len(df)
    df.to_csv(path, index=False, sep=";", encoding="utf-8-sig")
    return removed


def main():
    if not HIST_DIR.exists():
        print("No existe carpeta de históricos.")
        return

    files = sorted(HIST_DIR.glob("*_historico.csv"))
    if not files:
        print("No hay archivos *_historico.csv para deduplicar.")
        return

    total_removed = 0
    for f in files:
        removed = dedupe_file(f)
        total_removed += removed
        print(f"[OK] {f.name}: duplicados eliminados={removed}")

    print(f"Total duplicados eliminados: {total_removed}")


if __name__ == "__main__":
    main()