# LIB07 Scraper (IMN) - CSV/XLSX + GitHub Actions cada 15 min

Este proyecto extrae tablas de:

`https://www.imn.ac.cr/especial/tablas/lib07.html`

y genera archivos en formato LATAM:

- Separador de columnas: `;`
- Decimal: `,`
- Miles: `.`

## Archivos principales

- `export_lib07_csv.py`  
  Extrae tablas (`Horarios`, `Actuales_resumen`, `Actuales_inst`) y genera:
  - `salida_csv/lib07_horarios.csv`
  - `salida_csv/lib07_actuales_resumen.csv`
  - `salida_csv/lib07_actuales_instantanea.csv`
  - `salida_csv/lib07_tablas.xlsx`
  - además histórico en `salida_csv/historico/` con timestamp UTC.

- `cleanup_history.py`  
  Busca históricos antiguos (por defecto >30 días), envía correo con listado/adjunto ZIP y **solo si el correo se envía correctamente** elimina archivos viejos.

- `.github/workflows/scrape_lib07.yml`  
  Ejecuta todo cada 15 minutos (UTC), y hace commit/push si hubo cambios.

---

## Requisitos locales

```bash
pip install -r requirements.txt