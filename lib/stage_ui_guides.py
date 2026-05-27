"""Textos guiados para la UI de Operación (lenguaje no técnico)."""
from __future__ import annotations

from typing import Any

_GUIDES: dict[int, dict[str, Any]] = {
    0: {
        "title": "Crear la planilla Solicitud del mes",
        "summary": (
            "Toma el archivo maestro de pagos y la base de docentes, y genera "
            "Solicitud.xlsx en la carpeta del mes. Es el punto de partida del proceso."
        ),
        "steps": [
            {
                "id": "review",
                "title": "Revisar carpeta del mes",
                "detail": "Confirma que el mes y la carpeta existen y que hay un Excel maestro.",
            },
            {
                "id": "choose",
                "title": "Elegir archivos",
                "detail": "Selecciona el maestro del mes y la base BD-DOCENTES.",
            },
            {
                "id": "run",
                "title": "Generar Solicitud",
                "detail": "Se crea o actualiza Solicitud.xlsx. Luego revisa el resultado en Seguimiento.",
            },
        ],
    },
    1: {
        "title": "Enviar correos de solicitud de boleta",
        "summary": (
            "Avisa a los docentes que deben emitir su boleta. Sin marcar envío real "
            "solo revisa a quién iría el correo (como una vista previa)."
        ),
        "steps": [
            {"id": "review", "title": "Revisar Solicitud y adjunto PDF", "detail": "Debe existir Solicitud.xlsx y el PDF de ejemplo."},
            {"id": "choose", "title": "Decidir si envías correos reales", "detail": "Deja desmarcado «Enviar correos reales» para solo analizar."},
            {"id": "run", "title": "Ejecutar envíos", "detail": "Outlook debe estar abierto en este equipo si envías de verdad."},
        ],
    },
    2: {
        "title": "Descargar boletas desde el correo",
        "summary": (
            "Busca en Outlook los XML/PDF del período y los guarda en la carpeta del mes. "
            "Indica desde qué fecha hasta qué fecha revisar el buzón."
        ),
        "steps": [
            {"id": "review", "title": "Revisar fechas del mes", "detail": "Por defecto se usa todo el mes seleccionado (ej. 01/05 a 31/05)."},
            {"id": "choose", "title": "Ajustar fechas si hace falta", "detail": "Puedes acotar el rango con el calendario o escribiendo dd/mm/aaaa."},
            {"id": "run", "title": "Extraer adjuntos", "detail": "Los archivos quedan en la carpeta del mes; revisa el log al terminar."},
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
            "Envía confirmación solo a filas RECIBIDO. Importante: sin «Enviar correos reales» "
            "no se manda nada (modo prueba)."
        ),
        "steps": [
            {"id": "review", "title": "Revisar quién está RECIBIDO", "detail": "Mira el resumen de la planilla arriba."},
            {"id": "choose", "title": "Confirmar envío real", "detail": "Marca envío real solo cuando estés seguro."},
            {"id": "run", "title": "Enviar confirmaciones", "detail": "Cada correo usa los datos del XML en Solicitud."},
        ],
    },
    6: {
        "title": "Informe final de boletas",
        "summary": "Genera el informe consolidado del mes en Solicitud.",
        "steps": [
            {"id": "review", "title": "Revisar Solicitud", "detail": "Debe estar actualizado tras pasos anteriores."},
            {"id": "choose", "title": "Sin opciones extra", "detail": "Solo confirma el período correcto."},
            {"id": "run", "title": "Generar informe", "detail": "Revisa el log por advertencias."},
        ],
    },
    7: {
        "title": "Correos de información de pago",
        "summary": (
            "Lee la hoja Pagos y envía el detalle de depósito. Requiere fecha de pago y "
            "marcar envío real si corresponde."
        ),
        "steps": [
            {"id": "review", "title": "Revisar hoja Pagos", "detail": "Debe existir en Solicitud.xlsx."},
            {"id": "choose", "title": "Fecha de pago y envío", "detail": "Elige la fecha que verán los docentes."},
            {"id": "run", "title": "Enviar correos de pago", "detail": "Revisa montos en vista previa del script si dudas."},
        ],
    },
    8: {
        "title": "Separar boletas IP y CFT",
        "summary": (
            "Copia o mueve PDF/XML a subcarpetas IP y CFT según el mapa de clasificación. "
            "Elige el archivo CSV de mapeo en la carpeta del mes."
        ),
        "steps": [
            {"id": "review", "title": "Revisar archivos en la carpeta", "detail": "Deben estar los bhe_*.pdf/xml del mes."},
            {"id": "choose", "title": "Elegir CSV y modo", "detail": "map_ip_cft.csv clasifica cada RUT. Puedes simular sin mover."},
            {"id": "run", "title": "Separar archivos", "detail": "Revisa carpetas IP/ y CFT/ al finalizar."},
        ],
    },
    9: {
        "title": "Agrupar por docente",
        "summary": "Organiza archivos en carpetas por docente dentro de IP/CFT.",
        "steps": [
            {"id": "review", "title": "Revisar paso 8", "detail": "Primero deben existir carpetas IP/CFT con boletas."},
            {"id": "choose", "title": "Copiar archivos a carpetas docente", "detail": "Marca la opción si quieres copiar PDF/XML a cada carpeta."},
            {"id": "run", "title": "Agrupar", "detail": "Queda un resumen en logs_agrupa/."},
        ],
    },
    10: {
        "title": "Revisión final de carpetas",
        "summary": "Comprueba que cada docente tenga lo esperado y genera revision_carpetas.xlsx.",
        "steps": [
            {"id": "review", "title": "Revisar estructura IP/CFT", "detail": "Tras pasos 8 y 9."},
            {"id": "choose", "title": "Simular o forzar", "detail": "Simulación no escribe marcadores; forzar re-analiza todo."},
            {"id": "run", "title": "Generar revisión", "detail": "Abre revision_carpetas.xlsx al terminar."},
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
