import asyncio
import os
import requests
import json
import re
import aiohttp
import html
from dotenv import load_dotenv

from acciones.data import accionesjson


from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

import sys
from os import path

# Aseguramos que Python pueda ver la carpeta raíz del proyecto
sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

# Importación directa y limpia desde la carpeta hermana
from AI.ia import otto, ottochat, system_prompt, chat_prompt



timeout = aiohttp.ClientTimeout(total=5)
accionespermitidas = accionesjson()
iaMain = "llama3.1:8b"
iaSecond = "llama3.2:latest"
iaPhi = "phi3.5:3.8b-mini-instruct-q6_K"

# ------------ CONFIG ------------
telegram_ids_env = os.getenv("ALLOWED_TELEGRAM_IDS")
allowed_telegram_ids = [int(x.strip()) for x in telegram_ids_env.split(",") if x.strip().isdigit()]

TOKEN_TELEGRAM = os.getenv("TOKEN_TELEGRAM")

OLLAMA_URL = os.getenv("OLLAMA_URL")

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

    async def generar_respuesta_ollama(mensaje_usuario):
        print("☁️ [API] Generando charla conversacional con DeepSeek...")
        return ottochat(mensaje_usuario, chat_prompt())
    
    
    
else:
    async def generar_comando_otto(mensaje_usuario):
        print("🏠 [Local] Intentando extraer comando con Ollama...")
        url = os.getenv("OLLAMA_URL")
        payload = {
            "model": iaMain, # Tu modelo principal de comandos
            "prompt": f"{system_prompt()}\n\nOrden del usuario: {mensaje_usuario}",
            "stream": False,
            "options": {"temperature": 0.3} # Forzar consistencia JSON
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "").strip()
        except Exception as e:
            print(f"❌ Error en extractor Ollama local: {e}")
        return ""
    
    
    # ------------ BOT ------------
    async def generar_respuesta_ollama(prompt_usuario):
    # La URL apunta al puerto por defecto de Ollama en el mismo contenedor
        url = os.getenv("OLLAMA_URL")

        payload = {
            "model": iaPhi, # Asegúrate que sea el nombre exacto de 'ollama list'
            "prompt": prompt_usuario,
            "system": "Otto, el mejor asistente y usas el modelo " + iaPhi + ". Responde siempre en español y de manera conscisa",
            "stream": False,
            "options": {
                "num_predict": 80,  # Limita la respuesta a ~75-100 palabras
                "temperature": 0.8,   # Creatividad moderada
                "top_k": 20,          # Menos opciones para procesar más rápido
                "num_thread": 16       # Usa 4 hilos de tu CPU (ajusta según tu LXC)
            }
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("response", "Lo siento, recibí una respuesta vacía.")
                    else:
                        return f"Error de Ollama: Código de estado {response.status}"
        except Exception as e:
            return f"No pude conectar con la IA: {str(e)}"


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
                #
                #Estrcuturacion de los datos antes del envio al pc
                payload = {
                            "accion": accion,
                            "valor": valor
                        }
                
                
                
                # -------- Enviar a Flask --------
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.post(LAPTOP_API, json=payload, headers=API_HEADERS) as r:
                            
                            if r.status == 200:
                                try:
                                    api_resp = await r.json()
                                    msg = api_resp.get("msg", "OK")
                                except Exception:
                                    msg = await r.text()
    
                                print("respuesta de texto comando")
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
