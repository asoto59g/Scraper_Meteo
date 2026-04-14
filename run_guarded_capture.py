# run_guarded_capture.py
"""
Punto de entrada del scraper LIB07.

La deduplicación se maneja por 'fecha' directamente en export_lib07_csv.py:
cada ejecución inserta al histórico solo las horas del IMN que aún no están
registradas, sin importar cuántas veces corra el workflow.
"""
from export_lib07_csv import export_outputs


def main():
    export_outputs(debug=False)


if __name__ == "__main__":
    main()