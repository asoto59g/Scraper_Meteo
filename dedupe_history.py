# dedupe_history.py
from pathlib import Path
import pandas as pd

HIST_DIR = Path("salida_csv/historico")

def dedupe_file(path: Path):
    # Leer CSV histórico
    try:
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig")
    except Exception:
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8")

    if df.empty:
        return 0

    required = {"programado_slot", "captura_utc_real"}
    if not required.issubset(set(df.columns)):
        print(f"[SKIP] {path.name}: faltan columnas {required}")
        return 0

    before = len(df)

    # Parse fechas para ordenar correctamente
    df["_slot_dt"] = pd.to_datetime(df["programado_slot"], errors="coerce", utc=True)
    df["_real_dt"] = pd.to_datetime(df["captura_utc_real"], errors="coerce", utc=True)

    # Ordenar y quedarse con el más reciente por slot
    df = df.sort_values(by=["_slot_dt", "_real_dt"], ascending=[True, True])
    df = df.drop_duplicates(subset=["programado_slot"], keep="last")

    # Limpiar auxiliares y ordenar final
    df = df.sort_values(by=["_slot_dt"], ascending=True)
    df = df.drop(columns=["_slot_dt", "_real_dt"])

    after = len(df)
    removed = before - after

    # Guardar
    df.to_csv(path, index=False, sep=";", encoding="utf-8-sig")
    return removed

def main():
    if not HIST_DIR.exists():
        print("No existe carpeta de históricos.")
        return

    total_removed = 0
    files = list(HIST_DIR.glob("*_historico.csv"))

    if not files:
        print("No hay archivos *_historico.csv para deduplicar.")
        return

    for f in files:
        removed = dedupe_file(f)
        total_removed += removed
        print(f"[OK] {f.name}: duplicados eliminados={removed}")

    print(f"\nTotal duplicados eliminados: {total_removed}")

if __name__ == "__main__":
    main()