"""Comprueba que la clave de Gemini y el modelo del .env funcionan.

    python ia/probar_clave.py
"""
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
clave = os.getenv("GEMINI_API_KEY", "").strip()
modelo = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
BASE = "https://generativelanguage.googleapis.com/v1beta"

if not clave:
    raise SystemExit("Falta GEMINI_API_KEY en el .env")

cabeceras = {"x-goog-api-key": clave}
r = httpx.post(f"{BASE}/models/{modelo}:generateContent", headers=cabeceras, timeout=30,
               json={"contents": [{"parts": [{"text": "Responde solo con la palabra: listo"}]}]})

if r.status_code == 200:
    texto = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    print(f"OK. Modelo {modelo} respondió: {texto}")
else:
    print(f"Error {r.status_code} con el modelo {modelo}:")
    print(r.text[:400])
    # Si el modelo no existe o cambió de nombre, mostramos los que sí sirven
    lista = httpx.get(f"{BASE}/models", headers=cabeceras, timeout=30)
    if lista.status_code == 200:
        print("\nModelos disponibles para generar texto con tu clave:")
        for m in lista.json().get("models", []):
            if "generateContent" in m.get("supportedGenerationMethods", []):
                print(" -", m["name"].replace("models/", ""))
