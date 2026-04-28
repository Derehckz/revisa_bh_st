#!/usr/bin/env python3
"""
Script maestro para ejecutar el flujo de procesamiento de boletas de honorarios por etapas.
Permite ejecutar scripts en orden con pausas interactivas para control manual.
"""

import os
import sys
import subprocess
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
import config
import utils

console = Console()

SCRIPTS = [
    ("1.-envia_correo_mensual_bh.py", "Envío de correos iniciales"),
    ("2.-extrae_xml_correo.py", "Extracción de adjuntos XML/PDF"),
    ("3.-revisa_solicitud_VS_recibidas.py", "Validación solicitud vs recibidas"),
    ("4.-extrae_datos_xml_al_excel.py", "Extracción datos XML al Excel"),
    ("5.-Enviar_Correo_Recepcion.py", "Envío de correos de recepción"),
    ("6.-Informe_final_boletas.py", "Generación de informe final"),
    ("7.-Envia_mail_pagos.py", "Envío de mails de pagos"),
    ("8.-separa_bh_ip_cft.py", "Separación BH IP/CFT"),
    ("9.-agrupa_por_docente.py", "Agrupación por docente"),
    ("10.-revisa_carpetas_ip_cft.py", "Revisión de carpetas IP/CFT"),
]

def check_prerequisites(step, year=None, month=None):
    """Verifica pre-requisitos antes de ejecutar un script."""
    base_path = os.path.join(config.RAIZ, year, month) if year and month else None
    
    if step == 0:  # Script 1
        if not os.path.isfile(config.ARCHIVO_ADJUNTO):
            raise ValueError(f"Archivo adjunto no encontrado: {config.ARCHIVO_ADJUNTO}")
    
    elif step == 1:  # Script 2
        pass  # Requiere Outlook
    
    elif step == 2:  # Script 3
        if base_path and not any(f.endswith('.xlsx') for f in os.listdir(base_path) if os.path.isfile(os.path.join(base_path, f))):
            raise ValueError(f"No se encontró archivo Excel en {base_path}")
    
    elif step == 3:  # Script 4
        pass  # Ya verificado en script 3
    
    elif step == 4:  # Script 5
        if base_path:
            excel_path = os.path.join(base_path, "Solicitud.xlsx")
            if not os.path.isfile(excel_path):
                raise ValueError(f"Archivo Solicitud.xlsx no encontrado en {base_path}")
    
    # Agregar más checks según necesidad

def run_script(script_name, description, year=None, month=None):
    """Ejecuta un script con argumentos opcionales."""
    cmd = [sys.executable, script_name]
    if year:
        cmd.extend(["--year", year])
    if month:
        cmd.extend(["--month", month])

    console.print(f"[cyan]Ejecutando: {description}[/cyan]")
    result = subprocess.run(cmd, cwd=os.getcwd())
    if result.returncode != 0:
        raise RuntimeError(f"Error en {script_name}: {result.returncode}")
    console.print(f"[green]✅ Completado: {description}[/green]")

def main():
    parser = argparse.ArgumentParser(description="Flujo maestro de boletas de honorarios")
    parser.add_argument("--year", type=str, help="Año específico")
    parser.add_argument("--month", type=str, help="Mes específico")
    parser.add_argument("--start-from", type=int, choices=range(1, 11), help="Iniciar desde script N")
    parser.add_argument("--end-at", type=int, choices=range(1, 11), help="Terminar en script N")
    parser.add_argument("--non-interactive", action="store_true", help="Ejecutar sin pausas interactivas")
    args = parser.parse_args()

    console.print(Panel.fit("🚀 [bold cyan]FLUJO MAESTRO DE BOLETAS DE HONORARIOS[/bold cyan]", style="bold green"))

    start = args.start_from or 1
    end = args.end_at or 10

    for i, (script, desc) in enumerate(SCRIPTS, 1):
        if i < start or i > end:
            continue

        try:
            check_prerequisites(i-1, args.year, args.month)
            run_script(script, desc, args.year, args.month)
            
            if not args.non_interactive and i < end:
                console.print(f"\n[bold yellow]¿Continuar al siguiente paso ({i+1}: {SCRIPTS[i][1]})?[/bold yellow]")
                respuesta = input("Presione Enter para continuar, 'n' para detener: ").strip().lower()
                if respuesta == 'n':
                    console.print("[yellow]Flujo detenido por el usuario.[/yellow]")
                    break
        except Exception as e:
            console.print(f"[red]❌ Error en paso {i}: {e}[/red]")
            sys.exit(1)

    console.print(Panel.fit("🎉 [bold green]FLUJO COMPLETADO EXITOSAMENTE[/bold green]", style="bold blue"))

if __name__ == "__main__":
    main()