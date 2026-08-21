"""Textos guiados para la UI de Operación (lenguaje no técnico)."""
from __future__ import annotations

from typing import Any

_GUIDES: dict[int, dict[str, Any]] = {
    0: {
        "title": "Crear la planilla Solicitud del mes",
        "summary": (
            "Toma el archivo maestro de pagos y la base de docentes, y genera "
            "Solicitud.xlsx en la carpeta del mes. Antes de generar puedes ver "
            "qué boletas NO RECIBIDO de meses previos se agregarán como PROVISIONADO."
        ),
        "steps": [
            {
                "id": "review",
                "title": "Revisar carpeta del mes",
                "detail": "Confirma que el mes y la carpeta existen y que hay un Excel maestro.",
            },
            {
                "id": "choose",
                "title": "Elegir archivos y ver provisionados",
                "detail": (
                    "Selecciona el maestro y BD-DOCENTES. Revisa la tabla de arrastre: "
                    "esas filas se agregan al generar y cada una tendrá su propio correo."
                ),
            },
            {
                "id": "run",
                "title": "Generar Solicitud",
                "detail": (
                    "Se crea o actualiza Solicitud.xlsx con el maestro más las filas "
                    "PROVISIONADO. Luego envía correos en el paso 1."
                ),
            },
        ],
    },
    1: {
        "title": "Enviar correos de solicitud de boleta",
        "summary": (
            "Avisa a los docentes que deben emitir su boleta. Sin marcar envío real "
            "solo revisa a quién iría el correo (como una vista previa). "
            "Si ya enviaste solicitudes y solo faltan respuestas, usa «Solo recordatorios» "
            "(no reenvía el correo original)."
        ),
        "steps": [
            {"id": "review", "title": "Revisar Solicitud y adjunto PDF", "detail": "Debe existir Solicitud.xlsx y el PDF de ejemplo."},
            {
                "id": "choose",
                "title": "Envío inicial vs solo recordatorios",
                "detail": (
                    "Primera vez: marca «Enviar correos reales» para solicitar boletas. "
                    "Si ya pediste y hay NO RECIBIDO, marca «Solo recordatorios»."
                ),
            },
            {"id": "run", "title": "Ejecutar envíos", "detail": "Outlook debe estar abierto en este equipo si envías de verdad."},
        ],
    },
    2: {
        "title": "Descargar boletas desde el correo",
        "summary": (
            "Busca en Outlook los XML/PDF del período y los guarda en la carpeta del mes. "
            "Por defecto usa todo el mes: no acotes fechas sin motivo (se pierden boletas)."
        ),
        "steps": [
            {
                "id": "review",
                "title": "Revisar fechas del mes",
                "detail": "Por defecto se usa todo el mes seleccionado (ej. 01/08 a 31/08).",
            },
            {
                "id": "choose",
                "title": "Ampliar si llega fuera del mes",
                "detail": (
                    "Solo cambia el rango si sabes que hay correos antes/después del mes. "
                    "Acotar de más deja boletas como NO RECIBIDO."
                ),
            },
            {"id": "run", "title": "Extraer adjuntos", "detail": "Los archivos quedan en la carpeta del mes; no modifica Excel."},
        ],
    },
    3: {
        "title": "Comparar planilla vs boletas recibidas",
        "summary": "Marca en Solicitud quién está RECIBIDO o NO RECIBIDO según los XML en la carpeta.",
        "steps": [
            {"id": "review", "title": "Revisar que haya XML", "detail": "Si no hay XML, ejecuta antes el paso 2."},
            {"id": "choose", "title": "Opciones de validación", "detail": "«Validación estricta» exige que el Excel esté bien formado."},
            {"id": "run", "title": "Actualizar estados", "detail": "Se modifica Solicitud.xlsx con Estado_Recepcion."},
        ],
    },
    4: {
        "title": "Leer datos de los XML al Excel",
        "summary": "Rellena columnas del XML (montos, RUT, etc.) en Solicitud para las filas recibidas.",
        "steps": [
            {"id": "review", "title": "Revisar boletas recibidas", "detail": "Conviene tener el paso 3 listo."},
            {"id": "choose", "title": "Validación estricta (opcional)", "detail": "Actívala si quieres bloquear errores de formato."},
            {"id": "run", "title": "Extraer al Excel", "detail": "Puede tardar varios minutos según cantidad de XML."},
        ],
    },
    5: {
        "title": "Avisar recepción por correo",
        "summary": (
            "Confirmación técnica (calza con la Solicitud) o observación/reenvío si hay error. "
            "No es el visto bueno de Contabilidad: eso se marca en el checklist tras el informe."
        ),
        "steps": [
            {
                "id": "review",
                "title": "Elegir grupos",
                "detail": "Confirmaciones (técnicas), errores y/o reenvíos. Provisionados avisan que Contabilidad aún valida.",
            },
            {"id": "choose", "title": "Confirmar envío real", "detail": "Marca envío real solo cuando estés seguro."},
            {"id": "run", "title": "Enviar", "detail": "Solo se despacha a los grupos seleccionados."},
        ],
    },
    6: {
        "title": "Informe final de boletas",
        "summary": (
            "Genera el informe consolidado para enviar a Contabilidad. "
            "Cuando Contabilidad responda OK, márcalo en el checklist antes de cerrar el período."
        ),
        "steps": [
            {"id": "review", "title": "Revisar período", "detail": "Debe estar actualizado tras pasos anteriores."},
            {"id": "choose", "title": "Sin opciones extra", "detail": "Solo confirma el período correcto."},
            {
                "id": "run",
                "title": "Generar informe",
                "detail": "Envía el informe a Contabilidad; luego marca OK Contabilidad en Operación.",
            },
        ],
    },
    7: {
        "title": "Correos de información de pago",
        "summary": (
            "Pega o sube la tabla de Contabilidad (solo correo HTML/CSV), "
            "completa MAIL/SEDE desde Solicitud, previsualiza y envía el detalle de depósito."
        ),
        "steps": [
            {
                "id": "import",
                "title": "Cargar pagos Contabilidad",
                "detail": "Pega la tabla del correo o sube CSV/Excel; se agregan MAIL y SEDE.",
            },
            {
                "id": "choose",
                "title": "Fecha de pago",
                "detail": "La fecha que verán los docentes en el correo.",
            },
            {
                "id": "run",
                "title": "Previsualizar y enviar",
                "detail": "Revisa montos/correos y despacha por Outlook.",
            },
        ],
    },
    8: {
        "title": "Separar boletas IP y CFT",
        "summary": (
            "Organiza archivos del mes en carpetas IP/CFT según el mapa del período. "
            "Elige el CSV de mapeo en la carpeta del mes."
        ),
        "steps": [
            {"id": "review", "title": "Revisar archivos del período", "detail": "Deben estar los bhe_*.pdf/xml del mes."},
            {"id": "choose", "title": "Elegir CSV y modo", "detail": "map_ip_cft.csv clasifica cada RUT. Puedes simular sin mover."},
            {"id": "run", "title": "Separar archivos", "detail": "Revisa carpetas IP/ y CFT/ al finalizar."},
        ],
    },
    9: {
        "title": "Agrupar por docente",
        "summary": "Organiza archivos en carpetas por docente dentro de IP/CFT del período.",
        "steps": [
            {"id": "review", "title": "Revisar paso 8", "detail": "Primero deben existir carpetas IP/CFT con boletas."},
            {"id": "choose", "title": "Copiar archivos a carpetas docente", "detail": "Marca la opción si quieres copiar PDF/XML a cada carpeta."},
            {"id": "run", "title": "Agrupar", "detail": "Queda un resumen en logs_agrupa/."},
        ],
    },
    10: {
        "title": "Revisión final de carpetas",
        "summary": (
            "Comprueba que cada docente tenga lo esperado en el período "
            "y genera el artefacto revision_carpetas.xlsx."
        ),
        "steps": [
            {"id": "review", "title": "Revisar estructura IP/CFT", "detail": "Tras pasos 8 y 9."},
            {"id": "choose", "title": "Simular o forzar", "detail": "Simulación no escribe marcadores; forzar re-analiza todo."},
            {"id": "run", "title": "Generar revisión", "detail": "Revisa el artefacto al terminar."},
        ],
    },
}


def get_stage_guide(stage_num: int) -> dict[str, Any]:
    return _GUIDES.get(
        stage_num,
        {
            "title": f"Paso {stage_num}",
            "summary": "Ejecuta esta etapa del pipeline mensual.",
            "steps": [
                {"id": "review", "title": "Revisar", "detail": ""},
                {"id": "choose", "title": "Configurar", "detail": ""},
                {"id": "run", "title": "Ejecutar", "detail": ""},
            ],
        },
    )
