import asyncio
import os
import requests
import json
import re
import aiohttp
import io
from dotenv import load_dotenv
from pprint import pprint
import base64
import sys

from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from acciones.data import accionesjson
from AI.ia import otto, system_prompt, ottovisor, ollama, system_prompt_ollama
from os import path

# Aseguramos que Python pueda ver la carpeta raíz del proyecto
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))


timeout = aiohttp.ClientTimeout(total=5)
accionespermitidas = accionesjson()

iaM = "llama3.1:8b"
iaMain = "llama3.1:8b"
iaSecond = "llama3.2:latest"
iaPhi = "phi3.5:3.8b-mini-instruct-q6_K"

# ------------ CONFIG ------------
telegram_ids_env = os.getenv("ALLOWED_TELEGRAM_IDS")
allowed_telegram_ids = [int(x.strip()) for x in telegram_ids_env.split(",") if x.strip().isdigit()]

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")

OLLAMA_URL = os.getenv("OLLAMA_URL")

HA_WEBHOOK_URL = os.getenv("HA_WEBHOOK_URL")

LAPTOP_API = os.getenv("LAPTOP_API")

API_HEADERS = {
    "X-API-KEY": os.getenv("HEADER_KEY"),
    "Content-Type": "application/json"
}


def ollama_alive(url=os.getenv("OLLAMA_SHORT_URL")):
    """Comprueba de forma sincrónica y rápida si Ollama está corriendo."""
    try:
        # Hacemos un GET rápido con 1 segundo de timeout estricto
        respuesta = requests.get(url, timeout=1.0)
        return respuesta.status_code == 200
    except Exception:
        return False


forzar_nube = "--nube" in sys.argv

# Si el usuario forzó la nube, evitamos llamar a ollama_alive() para ahorrar tiempo
if forzar_nube:
    ia_local_disponible = False
else:
    ia_local_disponible = ollama_alive()

if not ia_local_disponible or forzar_nube:
    # --- RUTA NUBE PRINCIPAL ---
    async def generar_comando_otto(mensaje_usuario):
        print("☁️ [API] Intentando extraer comando con DeepSeek...")
        # Usa tu módulo ia.py importado (que ya tiene sus propios try/except)
        return otto(mensaje_usuario, system_prompt())
  
    
else:
    async def generar_comando_otto(mensaje_usuario):
        print("☁️ [API] Intentando extraer comando con ollama externo ...")
        # Usa tu módulo ia.py importado (que ya tiene sus propios try/except)
        respuesta = await ollama(mensaje_usuario, system_prompt_ollama(), iaMain)
        print("esto es desde la funcion")
        print(respuesta)
        return respuesta
    

async def manejar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_text = update.message.text
    if not user_text:
        return

    try:

        # ---------- OLLAMA ----------
        resAI = await generar_comando_otto(user_text)

        # -------- Extraer primer JSON válido --------
        
        
        try:
            # 1. Si la IA respondió un JSON válido, esto funcionará a la primera
            comando = json.loads(resAI)
            
    
            # 2ª Comprobación (Manual de Estructura): ¿Tiene el formato de un comando de Otto?
            if isinstance(comando, dict) and "accion" in comando:
                
                #logica de ejecucion
                datos_ia = comando
                            
                accion = datos_ia.get("accion")
                valor  = datos_ia.get("valor")
        
        
                # -------- Whitelist --------
        
                if accion not in accionespermitidas:
        
                    await update.message.reply_text(f"❌ Comando no valido o inexistente")
                    return
                
                if accion in ("crear_py"):
                    try:
                        payload = json.dumps({"accion": accion, "valor": valor})
                        pprint(payload)
                        # sys.exit()
                        
                    except:
                        await update.message.reply_text(
                            "No se pudo procesar."
                        )
                        return
                    
                    
                if accion in ("trabajar"):
                    
                    if valor not in ["portafolio", "propuestas_otto"]:
                        
                        await update.message.reply_text("No es carpeta valida.")
                        return  # Corta la ejecución aquí si no es válida
                        
                
                # -------- Sanear brillo/volumen --------
                if accion in ("brillo", "volumen"):
                
                    try:
                        valor = int(valor)
                        print("este es el valor")
                        print (valor)
        
                        if valor < 0:
                            await update.message.reply_text(
                                """⚠️ Comando reconocido, pero el valor está por 
                                debajo del rango válido."""
                            )
                            return
        
                        if valor > 100:
                            await update.message.reply_text(
                                """⚠️ Comando reconocido, pero el valor está por 
                                encima del rango válido."""
                            )
                            return
        
                    except:
                        await update.message.reply_text(
                            "Valor inválido."
                        )
                        return
                
                #Estructuracion de los datos antes del envio al pc
                payload = {
                            "accion": accion,
                            "valor": valor
                        }
                
                if accion in ("tv"):
                    # -------- Enviar a home assistant --------
                    try:
                        if valor not in ["encender", "apagar","musica"]:          
                            await update.message.reply_text("No es carpeta valida.")
                            return  # Corta la ejecución aquí si no es válida
                        
                        async with aiohttp.ClientSession(timeout=timeout) as session:
                            # Apuntamos a la URL de tu Webhook de Home Assistant
                            async with session.post(HA_WEBHOOK_URL, json=payload, headers=API_HEADERS) as r:
                                
                                if r.status == 200:
                                    print("Webhook ejecutado correctamente en Home Assistant")
                                    # Respuesta amigable para el usuario en Telegram
                                    await update.message.reply_text("📺 Comando enviado a la TV...")
    
                                else:
                                    await update.message.reply_text(f"❌ Error en Home Assistant: HTTP {r.status}")
    
                    except asyncio.TimeoutError:
                        await update.message.reply_text("⏱ Timeout: Home Assistant no respondió a tiempo.")
    
                    except aiohttp.ClientConnectorError:
                        await update.message.reply_text("🔌 No se pudo conectar con Home Assistant (revisa el túnel/red).")
    
                    except aiohttp.ClientError as e:
                        await update.message.reply_text(f"💥 Error de red: {e}")
                        
                    return
                
                
                
                # -------- Enviar a Flask --------
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(LAPTOP_API, json=payload, headers=API_HEADERS) as r:
                            
                            if r.status == 200:
                                try:
                                    # Intentamos parsear como JSON
                                    api_resp = await r.json()
                                    
                                    # 1. Comprobamos si la respuesta trae una captura de pantalla en base64
                                    if "image_base64" in api_resp:
                                        image_base64 = api_resp["image_base64"]
                                        
                                        # Procesamos con la IA
                                        descripcion = ottovisor(image_base64)
                                        
                                        # Reconstruimos los bytes para Telegram
                                        image_bytes = base64.b64decode(image_base64)
                                        image_file = io.BytesIO(image_bytes)
                                        image_file.name = "captura.png"
                                        
                                        await update.message.reply_photo(
                                            photo=image_file,
                                            caption=f"🤖 {descripcion}"
                                        )
                                    else:
                                        # 2. Si es un JSON normal de texto (como tenías antes)
                                        msg = api_resp.get("msg", "OK")
                                        print("Respuesta de texto comando")
                                        await update.message.reply_text(f"🤖 {msg}")
                                        
                                except Exception:
                                    # Por si acaso llega texto plano inesperado
                                    msg = await r.text()
                                    await update.message.reply_text(f"🤖 {msg}")
                                        
                            else:
                                await update.message.reply_text(f"❌ Error API {r.status}")
                                
                                
                except asyncio.TimeoutError:
                    await update.message.reply_text("⏱ Timeout con la laptop")
    
                except aiohttp.ClientConnectorError:
                    await update.message.reply_text("🔌 No conecta con la laptop")
    
                except aiohttp.ClientError as e:
                    await update.message.reply_text(f"💥 Error de red: {e}")
    
                return
    
            else:
                
                await update.message.chat.send_action(action="typing")
                
                await update.message.reply_text(
                    f"Acción no permitida: {comando}"
                )
                # return

        except json.JSONDecodeError:
            # aqui puedes cargar la logica de una IA local para que te genere una respuesta normal,
            # en modelos LLM pequeños algunas son buenas principalmente para estrcuturas json y otra para chat
            await update.message.chat.send_action(action="typing")
            await update.message.reply_text(resAI)
            
            return
        

    except Exception as e:

        await update.message.reply_text(
            f"💥 Error:\n{e}"
        )
        


# ------------ MAIN ------------

if __name__ == "__main__":

    app = (
        Application
        .builder()
        .token(TOKEN_TELEGRAM)
        .build()
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.User(user_id=allowed_telegram_ids),
            manejar_mensaje
        )
    )

    print("🚀 Escuchando...")
    app.run_polling()
