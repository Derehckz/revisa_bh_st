"""Escritura atómica de libros Excel: reemplazar una hoja preservando el resto."""
from __future__ import annotations

import gc
import logging
import os

import pandas as pd

import utils


def replace_sheet_atomically(ruta_excel: str, sheet_name: str, df_actualizado: pd.DataFrame) -> bool:
    """
    Sustituye `sheet_name` por `df_actualizado` y guarda el libro completo vía `atomic_excel_write`.
    """
    try:
        ruta_excel = os.path.abspath(ruta_excel)
        with pd.ExcelFile(ruta_excel, engine="openpyxl") as xls:
            hojas = {
                nombre: pd.read_excel(xls, sheet_name=nombre)
                for nombre in xls.sheet_names
            }
        hojas[sheet_name] = df_actualizado
        del df_actualizado
        gc.collect()

        def _writer(tmp_path: str) -> None:
            with pd.ExcelWriter(tmp_path, engine="openpyxl", mode="w") as writer:
                for nombre_hoja, df_hoja in hojas.items():
                    df_hoja.to_excel(writer, index=False, sheet_name=nombre_hoja)

        utils.atomic_excel_write(ruta_excel, _writer)
        return True
    except (OSError, IOError, PermissionError, ValueError, KeyError) as e:
        logging.error("[bh-excel] replace_sheet_atomically falló: %s", e)
        utils.print_error(
            f"No se pudo guardar el Excel. {e} "
            "Cierre Excel y cualquier vista previa del archivo en el Explorador."
        )
        return False
