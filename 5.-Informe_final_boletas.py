import os
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from colorama import init
import config
import utils

init(autoreset=True)
console = Console()

RAIZ = config.RAIZ

def seleccionar_opcion(lista, mensaje, icono=""):
    return utils.seleccionar_opcion(lista, mensaje, icono)

def obtener_ins(location):
    if str(location) == "508":
        return "IPS"
    elif str(location) == "114":
        return "CFT"
    else:
        return ""

def obtener_nombre_sede(location):
    if str(location) in ["508", "114"]:
        return "Matriz LL"
    else:
        return ""

def formatear_fecha(fecha):
    try:
        if pd.isna(fecha) or str(fecha).strip() == "":
            return ""
        fecha_str = str(int(fecha)).strip()
        if len(fecha_str) == 8:
            anio = fecha_str[0:4]
            mes = fecha_str[4:6]
            dia = fecha_str[6:8]
            return f"{dia}/{mes}/{anio}"
        else:
            return ""
    except (ValueError, TypeError):
        return ""

def determinar_tipo_pago(observacion):
    obs = str(observacion).strip().upper()
    if "OK; OJO ES PROVISIONADO" in obs:
        return "Boleta Pago Provisionado"
    elif "OK" in obs:
        return "Boleta Pago Normal"
    else:
        return ""

def formatear_tipo_doc(valor):
    try:
        v = float(valor)
        if v == 14.5:
            return "BER( 14,50% )"
        elif v == 17.5:
            return "BR( 17,50% )"
        else:
            return str(valor)
    except (ValueError, TypeError):
        return str(valor)
    
def formatear_rut(rut):
    rut_str = str(rut).strip()
    if len(rut_str) == 9:
        rut_str = "0" + rut_str
    if rut_str[-1:].lower() == 'k':
        rut_str = rut_str[:-1] + 'K'
    return rut_str

def main():
    console.print(Panel.fit("[bold cyan]📂 Selección de Excel y creación hoja resumen[/bold cyan]", style="bold green"))

    años = [d for d in os.listdir(RAIZ) if os.path.isdir(os.path.join(RAIZ, d))]
    if not años:
        console.print(Panel.fit("[red]⚠️ No hay carpetas de año en la ruta configurada.[/red]", style="bold red"))
        return
    año = seleccionar_opcion(sorted(años), "Seleccione el año:", "🗓️")
    ruta_año = os.path.join(RAIZ, año)

    meses = [d for d in os.listdir(ruta_año) if os.path.isdir(os.path.join(ruta_año, d))]
    if not meses:
        console.print(Panel.fit(f"[red]⚠️ No hay carpetas de mes en {ruta_año}[/red]", style="bold red"))
        return
    mes = seleccionar_opcion(sorted(meses), "Seleccione el mes:", "🗓️")
    ruta_mes = os.path.join(ruta_año, mes)

    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        console.print(Panel.fit(f"[red]⚠️ No se encontró archivo Excel en {ruta_excel}[/red]", style="bold red"))
        return

    df = pd.read_excel(ruta_excel, sheet_name=None, engine='openpyxl')
    hojas = list(df.keys())
    hoja = seleccionar_opcion(hojas, "Seleccione la hoja del Excel a procesar:", "📄")
    df_hoja = df[hoja]

    df_filtrado = df_hoja[df_hoja['Observaciones_XML'].str.strip().str.upper() == "DATOS EXTRAÍDOS OK"].copy()

    datos_resumen = []
    for _, fila in df_filtrado.iterrows():
        fecha_formateada = formatear_fecha(fila.get("fechaBoleta_XML", ""))
        tipo_pago = determinar_tipo_pago(fila.get("Observaciones", ""))
        ins = obtener_ins(fila.get("LOCATION", ""))
        nombre_sede = obtener_nombre_sede(fila.get("LOCATION", ""))
        tipo_doc_formateado = formatear_tipo_doc(fila.get("porcentajeImpuesto_XML", ""))

        nueva_fila = {
            "RUT": formatear_rut(fila.get("EMPLID", "")),
            "Nombre Docente": fila.get("NAME", ""),
            "Reg empleo": fila.get("EMPL_RCD", ""),
            "LOCATION": fila.get("LOCATION", ""),
            "INS": ins,
            "Nombre Sede": nombre_sede,
            "N° Boleta": fila.get("numeroBoleta_XML", ""),
            "Tipo Doc": tipo_doc_formateado,
            "Tipo de Pago": tipo_pago,
            "Fecha emisión": fecha_formateada,
            "Monto Bruto": fila.get("totalHonorarios_XML", "")
        }
        datos_resumen.append(nueva_fila)

    df_resumen = pd.DataFrame(datos_resumen)

    columnas_final = [
        "RUT", "Nombre Docente", "Reg empleo", "LOCATION", "INS", "Nombre Sede",
        "N° Boleta", "Tipo Doc", "Tipo de Pago", "Fecha emisión", "Monto Bruto"
    ]
    df_resumen = df_resumen[columnas_final]

    try:
        # Backup previo del Excel antes de sobrescribir
        try:
            utils.backup_file(ruta_excel)
        except OSError:
            pass
        with pd.ExcelWriter(ruta_excel, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_resumen.to_excel(writer, index=False, sheet_name="Resumen Boletas")
        console.print(Panel.fit(f"[green]✔️ Hoja 'Resumen Boletas' sobrescrita correctamente en {ruta_excel}[/green]", style="bold green"))
    except (OSError, IOError, PermissionError) as e:
        console.print(Panel.fit(f"[red]⚠️ Error guardando Excel: {e}[/red]", style="bold red"))

if __name__ == "__main__":
    main()
