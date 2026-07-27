import json
import os


def accionesjson():
    # 1. Obtiene la ruta de la carpeta donde vive ESTE archivo (data.py)
    carpeta_actual = os.path.dirname(__file__)

    # 2. Une esa carpeta con el nombre del archivo JSON
    ruta_absoluta = os.path.join(carpeta_actual, "acciones.json")

    # 3. Abre el archivo usando la ruta absoluta calculada
    with open(ruta_absoluta, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    accionespermitidas = datos["acciones"]
    
    return accionespermitidas

