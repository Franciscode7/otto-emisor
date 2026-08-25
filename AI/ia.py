import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import base64
import aiohttp
import asyncio
import sys

# Dentro de AI/ia.py
# Esto sube una carpeta desde AI (llegando a otto-emisor) y la agrega al sistema
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from acciones.data import accionesjson

config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.md'))

# Función rápida para leerlo cuando lo necesites
def leer_config():
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return None

accionespermitidas = accionesjson()

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

    ruta_config = leer_config()
    
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

def system_prompt_ollama():
    return obtener_comportamiento("COMPORTAMIENTO_COMANDOS_Local")

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
            temperature=0.8 
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
    
    
def ottovisor(archivo: str):
    
    try:
        respuesta = client.chat.completions.create(
            model="deepseek-v4-flash-vision-exp",
            # Aquí metemos el sistema y tu mensaje directo sin depender de variables externas
              messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe la imagen, se breve"},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{archivo}"},
                            },
                        ],
                    }
                ],
            temperature=0.8 
        )
 
        # ... código de la petición ...
        ia_respuesta = respuesta.choices[0].message.content

        print(ia_respuesta)
        return ia_respuesta
        
    except Exception as e:
        print(f"❌ Error al conectar con Otto: {e}")
        return None
    
async def ollama(mensaje: str, prompt_entrada: str, ia: str):
    print("🏠 [Local] Intentando extraer comando con Ollama...")
    url = os.getenv("OLLAMA_URL")
    
    prompt_final = f"### Sistema:\n{prompt_entrada}\n\n### Usuario:\n{mensaje}\n\n### Modelo IA usado:\n{ia}"
    
    payload = {
        "model": ia, # Tu modelo principal de comandos
        "prompt": prompt_final,
        "stream": False,
        "options": {"temperature": 0.1}
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=120) as response:
                if response.status == 200:
                    data = await response.json()
                    print("intento de respuesta:")
                    respuesta = (data.get("response", "").strip())
                    
                    try:
                        # Intentamos parsear la respuesta como JSON
                        comando = json.loads(respuesta)
                        print(comando)
                        accion = comando.get("accion")
                        
                        if accion not in accionespermitidas:
                            print ("comando no permitido")
                            chatOllama = await ollamachat(mensaje, chat_prompt(), ia)
                            return chatOllama
                        else:
                            return respuesta
                        
                    except json.JSONDecodeError:
                        # Si falla el parseo, significa que Otto decidió responder como chat normal
                        chatOllama = await ollamachat(mensaje, chat_prompt(), ia)
                        return chatOllama
    except Exception as e:
        print(f"❌ Error en extractor Ollama local: {e}")
    return ""


async def ollamachat(mensaje: str, prompt_entrada: str, ia: str):
    print("🏠 [Local] Intentando conversacion con Ollama...")
    url = os.getenv("OLLAMA_URL")
    
    prompt_final = f"### Sistema:\n{prompt_entrada}\n\n### Usuario:\n{mensaje}\n\n### Modelo IA usado:\n{ia}"
    
    payload = {
        "model": ia, # Tu modelo principal de comandos
        "prompt": prompt_final,
        "stream": False,
        "options": {"temperature": 0.8}
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    print("intento de respuesta:")
                    respuesta = (data.get("response", "").strip())
                    return respuesta
                
    except Exception as e:
        print(f"❌ Error en extractor Ollama local: {e}")
    return ""

# async def main():
#     iaMain = "phi3.5:3.8b-mini-instruct-q6_K"
#     userpromt = input("¿Que vamos a hacer?: ")
#     resultado = await ollama(userpromt, system_prompt_ollama(), iaMain)
#     print(resultado)

# if __name__ == "__main__":
#     # asyncio.run() es el motor que arranca el mundo asíncrono en Python
#     asyncio.run(main())
    
# chat_prompt()
    