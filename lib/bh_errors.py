"""Códigos de error homogéneos para mensajes operativos (prefijo [BH-CODIGO])."""


def format_bh(code: str, detail: str) -> str:
    code = (code or "ERR").strip().upper().replace(" ", "_")
    return f"[BH-{code}] {detail}"
