import pandas as pd

import schema_validator


def test_validate_stage1_missing_column_errors():
    df = pd.DataFrame({"EMPLID": [1], "RUT_SIN_DV": ["123"]})
    errors, warnings = schema_validator.validate_for_stage(df, "stage1_envio_inicial")
    assert any("Columna requerida ausente" in e for e in errors)
    assert "Email_Docente" in "".join(errors)


def test_validate_stage1_ok_minimal_columns():
    cols = schema_validator.CANONICAL_SCHEMA["stage1_envio_inicial"]
    data = {c: [""] for c in cols}
    df = pd.DataFrame(data)
    errors, _warnings = schema_validator.validate_for_stage(df, "stage1_envio_inicial")
    assert errors == []


def test_find_sheet_alias():
    hojas = ["otra", "SOLICITUD ", "Resumen de Boletas"]
    assert schema_validator.find_sheet(hojas, "Solicitud") == "SOLICITUD "
