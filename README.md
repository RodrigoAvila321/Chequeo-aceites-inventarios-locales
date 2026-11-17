# Control de Aceites: programa de escritorio

Programa en Python con interfaz gráfica, distribuible como ejecutable de Windows (`ControlAceites.exe`). Sirve para
cuadrar en litros el stock de lubricantes de un turno (tarros de 208 L + camión lubricador), descontar los consumos de
la semana, calcular el sobrante y compararlo con el stock que entrega el turno al finalizar. Detecta inconsistencias y
genera un reporte PDF.

Los aceites corresponden a los del proyecto **Planificación PM** (repositorio *Prueba*). LL-000X es el código de
compra; los nombres vienen de la hoja Configuración del Excel `Planificacion_PM.xlsm` y van incluidos en el programa:

| Código | Lubricante |
|---|---|
| LL-0001 | Mobil Delvac MX 15W40 |
| LL-0002 | M. Lube HD Plus 75W90 |
| LL-0003 | Mobil SHC Rarus 46 |
| LL-0004 | Mobil DTE 10 Excel 46 |
| LL-0005 | Mobil SHC Gear 320 |
| LL-0006 | Mobil Almo 529 |
| LL-0007 | Mobil Mining Coolant 50% |

Si cambian, **Configuración > Leer desde Planificación PM** los actualiza desde el Excel (`.xlsm`) o desde la base
`PlanificacionPM_datos.db`, **en modo solo lectura**: esos archivos nunca se modifican.

Diseño propio «grafito + ámbar»: fondo oscuro tipo tablero de taller, acentos color aceite y navegación por pestañas
superiores.

## Obtener el ejecutable

Cada `push` compila el `.exe` en GitHub Actions (workflow **Compilar ejecutable Windows**):

- **Release:** pestaña *Releases* del repositorio, descargue `ControlAceites.exe` en «Assets».
- **Artefacto:** pestaña *Actions*, abra la última ejecución correcta y descargue **ControlAceites-windows**.

Para compilarlo en Windows sin GitHub: instale Python 3.12 desde python.org (marque «Add python.exe to PATH») y haga
doble clic en `compilar_windows.bat`. El ejecutable queda en `dist\ControlAceites.exe`. Equivale a:

```bash
pip install -r requirements-dev.txt
python -c "from control_aceites.tema import guardar_ico; guardar_ico('icono.ico')"
pyinstaller --noconfirm --onefile --windowed --icon icono.ico --name ControlAceites main.py
```

Para ejecutarlo sin compilar: `pip install -r requirements.txt` y luego `python main.py`.

## Flujo de uso (pantalla «Control semanal»)

| Paso | Botón | Qué hace |
|---|---|---|
| 1 | **Stock inicial** | Pregunta a qué turno corresponde el stock (Turno A / Turno B) y pide, por aceite, los **tarros llenos** (× 208 L) y los **litros en el camión lubricador** indicados por el jefe de operaciones. |
| — | **Recepción de aceites** | Durante la semana, cada vez que llegan aceites: fecha, turno, observaciones y **tarros llenos recibidos** por aceite. Se pueden registrar varias recepciones y eliminarlas. |
| 2 | **Consumos semana** | Litros totales consumidos por aceite durante la semana y **tarros rellenados al camión**. Muestra el cálculo en vivo. |
| 3 | *(automático)* | Informa el **sobrante calculado** por aceite: tarros, litros en camión, total y equivalencia en tarros. |
| 4 | **Stock entregado** | Conteo físico entregado al finalizar el turno. Se compara contra el sobrante calculado. |
| 5 | **Reporte PDF** | Si hay inconsistencias, se ofrece de inmediato. Incluye datos del turno, indicadores, detalle por aceite, cuadratura de rellenos, hallazgos, conclusión y firmas. |

**Nuevo control** comienza otro ciclo y puede usar el stock entregado como stock inicial del siguiente. Los controles
quedan en **Historial**, donde se pueden abrir, reimprimir o eliminar.

## Reglas de cálculo (todo en litros)

- Stock = tarros × 208 L + litros en camión.
- **Recepciones:** los tarros recibidos se suman al stock de tarros. Sobrante = inicial + recibido − consumo. Los
  tarros recibidos también se pueden rellenar al camión.
- **Relleno al camión:** cada tarro vaciado resta 208 L a los tarros y suma 208 L al camión (balance 0 L). Se verifica
  que *stock inicial − consumo = sobrante calculado* en cada aceite.
- El consumo sale del camión. Si supera lo que hay en el camión, se descuentan tarros completos (relleno no registrado)
  y se avisa. Si supera el stock total, se marca como error.
- Al recibir el stock entregado se informa **cualquier diferencia**:
  - **Cuadrado:** tarros y camión coinciden.
  - **Cuadra en litros:** faltan tarros, pero su volumen aparece en el camión, es decir, tarros vaciados o cargados en
    el camión sin registrarse. No es pérdida. También detecta el caso inverso: un relleno registrado que no se hizo.
  - **Faltante / Sobrante:** diferencia neta en litros. Se informa además qué parte se explica por traspasos.
  - Si sobran tarros completos, se sugiere una **recepción no registrada**; si faltan tarros de un aceite que tuvo
    recepciones, se sugiere revisar si esa recepción realmente llegó.

## Datos

- `Documentos\ControlAceites\ControlAceites_datos.db`. Si junto al `.exe` existe un `ControlAceites_datos.db`, se usa
  ese (modo portátil).
- Los reportes se proponen en `Documentos\ControlAceites\Reportes`.
- **Configuración:** leer aceites desde Planificación PM (`.xlsm` o `.db`), activar o desactivar aceites, editar
  nombres, litros por tarro y respaldo de la base de datos.

## Estructura

```
main.py                     punto de entrada
control_aceites/
  calculo.py                sobrante, cuadratura en litros y análisis de inconsistencias
  catalogo.py               lectura (solo lectura) de los aceites de Planificación PM
  db.py                     base de datos SQLite local
  reporte_pdf.py            reporte PDF
  app.py, dialogos.py,
  widgets.py, tema.py       interfaz gráfica (Tkinter) y diseño de mantenimiento
tests/                      pruebas (pytest)
```

```bash
python -m pytest -q tests
```
