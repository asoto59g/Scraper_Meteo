# cleanup_history.py
import os
import smtplib
import zipfile
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import pandas as pd

HIST_DIR = Path("salida_csv/historico")
DAYS_TO_KEEP = int(os.getenv("DAYS_TO_KEEP", "30"))
MAX_ATTACH_MB = int(os.getenv("MAX_ATTACH_MB", "20"))

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
EMAIL_TO = os.getenv("EMAIL_TO", "oasotob@gmail.com")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def read_csv_robust(file: Path) -> pd.DataFrame:
    # tolerante a filas mal formadas
    try:
        return pd.read_csv(
            file, sep=";", dtype=str, encoding="utf-8-sig",
            engine="python", on_bad_lines="skip"
        )
    except Exception:
        return pd.read_csv(
            file, sep=";", dtype=str, encoding="utf-8",
            engine="python", on_bad_lines="skip"
        )


def parse_dt_utc(series):
    return pd.to_datetime(series, format="%Y-%m-%d %H:%M:%S", errors="coerce", utc=True)


def collect_old_rows():
    results = []
    total_old_rows = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_TO_KEEP)

    if not HIST_DIR.exists():
        return results, total_old_rows

    for file in HIST_DIR.glob("*_historico.csv"):
        df = read_csv_robust(file)
        if df.empty:
            continue

        if "captura_utc_real" in df.columns:
            ts = parse_dt_utc(df["captura_utc_real"])
        elif "captura_utc" in df.columns:
            ts = parse_dt_utc(df["captura_utc"])
        else:
            continue

        old_mask = ts < cutoff
        old_count = int(old_mask.sum())

        if old_count > 0:
            results.append({
                "file": file,
                "df_old": df[old_mask].copy(),
                "df_keep": df[~old_mask].copy(),
                "old_count": old_count,
                "total_count": len(df),
            })
            total_old_rows += old_count

    return results, total_old_rows


def build_zip_bytes(results):
    mem = BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in results:
            out_name = item["file"].stem + "_rows_to_delete.csv"
            csv_bytes = item["df_old"].to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
            zf.writestr(out_name, csv_bytes)
    mem.seek(0)
    return mem.read()


def send_email(results, total_old_rows, attach_zip_bytes=None):
    if not EMAIL_USER or not EMAIL_APP_PASSWORD:
        raise RuntimeError("Faltan EMAIL_USER o EMAIL_APP_PASSWORD en variables de entorno.")

    msg = EmailMessage()
    msg["Subject"] = f"LIB07 limpieza histórico: {total_old_rows} filas antiguas"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    detail = []
    for item in results:
        detail.append(f"- {item['file'].name}: eliminar {item['old_count']} / total {item['total_count']}")

    body = (
        f"Se detectaron filas antiguas (> {DAYS_TO_KEEP} días).\n\n"
        "Detalle:\n" + "\n".join(detail) +
        f"\n\nFecha UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    msg.set_content(body)

    if attach_zip_bytes:
        msg.add_attachment(
            attach_zip_bytes,
            maintype="application",
            subtype="zip",
            filename="lib07_rows_to_delete.zip",
        )

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(EMAIL_USER, EMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def apply_cleanup(results):
    for item in results:
        item["df_keep"].to_csv(item["file"], index=False, sep=";", encoding="utf-8-sig")


def main():
    results, total_old_rows = collect_old_rows()

    if total_old_rows == 0:
        print("No hay filas antiguas para limpiar.")
        return

    zip_bytes = build_zip_bytes(results)
    zip_mb = len(zip_bytes) / (1024 * 1024)

    if zip_mb <= MAX_ATTACH_MB:
        send_email(results, total_old_rows, attach_zip_bytes=zip_bytes)
        print(f"Correo enviado con ZIP ({zip_mb:.2f} MB).")
    else:
        send_email(results, total_old_rows, attach_zip_bytes=None)
        print(f"Correo enviado sin ZIP (ZIP {zip_mb:.2f} MB > {MAX_ATTACH_MB} MB).")

    # solo limpia si correo fue OK
    apply_cleanup(results)
    print(f"Limpieza aplicada. Filas eliminadas: {total_old_rows}")


if __name__ == "__main__":
    main()