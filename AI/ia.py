import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com/v1"
)



def es_json(cadena):
    """Devuelve True si la cadena es un JSON válido, False si es texto normal."""
    try:
        json.loads(cadena)
        return True
    except (json.JSONDecodeError, TypeError):
        return False
    
def obtener_comportamiento(tipo, ruta_archivo="config.md"):

    ruta_config = os.path.normpath(os.getenv("CONFIG_MD_PATH", "config.md"))
    
    try:
        with open(ruta_config, "r", encoding="utf-8") as f:
            contenido = f.read()
        
        # Esta expresión regular busca "# COMPORTAMIENTO_TU_TIPO" y agarra todo el texto de abajo
        patron = rf"#\s*{tipo}\s*\n(.*?)(?=\n#|$)"
        resultado = re.search(patron, contenido, re.DOTALL | re.IGNORECASE)
        
        if resultado:
            return resultado.group(1).strip()
        else:
            print(f"⚠️ No se encontró el comportamiento: {tipo}")
            return "Eres un asistente de IA."
            
    except FileNotFoundError:
        print(f"⚠️ Error: No se encontró {ruta_config}")
        return "Eres un asistente de IA."

def system_prompt():
    return obtener_comportamiento("COMPORTAMIENTO_COMANDOS")

def chat_prompt():
    return obtener_comportamiento("COMPORTAMIENTO_CHAT") 
    
def ottochat(mensaje: str, prompt_entrada: str):
    
    if not mensaje:
        return None
        
    prompt = prompt_entrada
    
    try:
        respuesta = client.chat.completions.create(
            model="deepseek-v4-flash",
            # Aquí metemos el sistema y tu mensaje directo sin depender de variables externas
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": mensaje}
            ],
            temperature=0.8  # Excelente para mantenerlo estricto con el formato JSON
        )

        # ... código de la petición ...
        ia_respuesta = respuesta.choices[0].message.content

        print(ia_respuesta)
        return ia_respuesta
        
    except Exception as e:
        print(f"❌ Error al conectar con Otto: {e}")
        return None


def otto(mensaje: str, prompt_entrada: str ):
    
    if not mensaje:
        return None
        
    prompt = prompt_entrada
    
    try:
        respuesta = client.chat.completions.create(
            model="deepseek-v4-flash",
            # Aquí metemos el sistema y tu mensaje directo sin depender de variables externas
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": mensaje}
            ],
            temperature=0.5  # Excelente para mantenerlo estricto con el formato JSON
        )

        # ... código de la petición ...
        ia_respuesta = respuesta.choices[0].message.content

        # Intentar interpretar si Otto nos devolvió un comando estructurado
        try:
            # Intentamos parsear la respuesta como JSON
            comando = json.loads(ia_respuesta)
            print (ia_respuesta)
            return ia_respuesta
            
        except json.JSONDecodeError:
            # Si falla el parseo, significa que Otto decidió responder como chat normal
            return ottochat(mensaje, chat_prompt())
        
    except Exception as e:
        print(f"❌ Error al conectar con Otto: {e}")
        return None

# if __name__ == "__main__":
#     otto("crea una funcion de suma en js", system_prompt())
    