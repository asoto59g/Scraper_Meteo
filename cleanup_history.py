# cleanup_history.py
import os
import smtplib
import zipfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

HIST_DIR = Path("salida_csv/historico")
DAYS_TO_KEEP = int(os.getenv("DAYS_TO_KEEP", "30"))
MAX_ATTACH_MB = int(os.getenv("MAX_ATTACH_MB", "20"))

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

EMAIL_USER = os.getenv("EMAIL_USER")               # tu gmail
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")  # app password
EMAIL_TO = os.getenv("EMAIL_TO", "oasotob@gmail.com")


def get_old_files():
    if not HIST_DIR.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_TO_KEEP)
    old = []
    for f in HIST_DIR.glob("*"):
        if f.is_file():
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                old.append(f)
    return sorted(old)


def build_zip(files, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, arcname=f.name)
    return zip_path.stat().st_size


def send_email(files, zip_path=None):
    if not EMAIL_USER or not EMAIL_APP_PASSWORD:
        raise RuntimeError("Faltan EMAIL_USER o EMAIL_APP_PASSWORD en variables de entorno.")

    msg = EmailMessage()
    msg["Subject"] = f"LIB07 - Archivos a eliminar ({len(files)})"
    msg["From"] = EMAIL_USER
    msg["To"] = EMAIL_TO

    lines = "\n".join([f"- {f.name}" for f in files[:200]])
    body = (
        f"Se detectaron {len(files)} archivos históricos mayores a {DAYS_TO_KEEP} días.\n\n"
        f"Listado (máx 200):\n{lines}\n\n"
        f"Fecha UTC: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"
    )
    msg.set_content(body)

    if zip_path and zip_path.exists():
        data = zip_path.read_bytes()
        msg.add_attachment(
            data,
            maintype="application",
            subtype="zip",
            filename=zip_path.name
        )

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(EMAIL_USER, EMAIL_APP_PASSWORD)
        smtp.send_message(msg)


def main():
    files = get_old_files()
    if not files:
        print("No hay archivos viejos para eliminar.")
        return

    tmp_zip = Path("to_delete_lib07.zip")
    zip_size = build_zip(files, tmp_zip)
    max_bytes = MAX_ATTACH_MB * 1024 * 1024

    try:
        if zip_size <= max_bytes:
            send_email(files, tmp_zip)
            print(f"Correo enviado con ZIP ({zip_size/1024/1024:.2f} MB).")
        else:
            # si pesa mucho, enviar solo listado (sin adjunto)
            send_email(files, zip_path=None)
            print(f"Correo enviado sin ZIP (ZIP excede {MAX_ATTACH_MB} MB).")

        # borrar SOLO si correo fue exitoso
        for f in files:
            f.unlink(missing_ok=True)
        print(f"Eliminados {len(files)} archivos históricos.")
    finally:
        if tmp_zip.exists():
            tmp_zip.unlink(missing_ok=True)


if __name__ == "__main__":
    main()