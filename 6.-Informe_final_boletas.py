import os
import pandas as pd
import config
import utils

RAIZ = config.RAIZ

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
    utils.print_header("📂 Selección de Excel y creación hoja resumen", "Generando hoja resumen de boletas")
    utils.print_step(1, 4, "Selección de período")

    try:
        año, mes = utils.seleccionar_año_mes(RAIZ)
    except ValueError as e:
        utils.print_error(str(e))
        return
    ruta_mes = os.path.join(RAIZ, año, mes)

    ruta_excel = os.path.join(ruta_mes, "Solicitud.xlsx")
    if not os.path.isfile(ruta_excel):
        utils.print_error(f"No se encontró archivo Excel en {ruta_excel}")
        return

    utils.print_step(2, 4, "Lectura y filtrado de datos")
    df = pd.read_excel(ruta_excel, sheet_name=None, engine='openpyxl')
    hojas = list(df.keys())
    hoja = utils.seleccionar_opcion(hojas, "Seleccione la hoja del Excel a procesar:", "📄")
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

    utils.print_step(3, 4, "Guardando hoja resumen")
    try:
        # Backup previo del Excel antes de sobrescribir
        try:
            utils.backup_file(ruta_excel)
        except OSError:
            pass
        with pd.ExcelWriter(ruta_excel, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df_resumen.to_excel(writer, index=False, sheet_name="Resumen Boletas")
        utils.print_success(f"Hoja 'Resumen Boletas' sobrescrita correctamente en {ruta_excel}")
    except (OSError, IOError, PermissionError) as e:
        utils.print_error(f"Error guardando Excel: {e}")
        return

    utils.print_step(4, 4, "Proceso completado")
    utils.print_success("Informe final de boletas generado correctamente.")

if __name__ == "__main__":
    main()
