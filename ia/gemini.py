"""Cliente mínimo de Gemini (API REST). Reintenta y cambia al modelo de respaldo si el principal falla."""
import os
import time

import httpx

BASE = "https://generativelanguage.googleapis.com/v1beta"
REINTENTABLES = {429, 500, 502, 503, 504}


class ErrorIA(Exception):
    """No se pudo obtener respuesta de ningún modelo."""


def _modelos():
    lista = [os.getenv("GEMINI_MODEL", "").strip(), os.getenv("GEMINI_MODEL_RESPALDO", "").strip()]
    return [m for i, m in enumerate(lista) if m and m not in lista[:i]]


def _texto(respuesta_json):
    try:
        partes = respuesta_json["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise ErrorIA("Gemini no devolvió texto (posible bloqueo de contenido)")
    texto = "".join(p.get("text", "") for p in partes if not p.get("thought")).strip()
    if not texto:
        raise ErrorIA("Gemini devolvió una respuesta vacía")
    return texto


def generar(prompt, sistema, como_json=False, intentos=2, espera=1.5):
    """Devuelve (texto, modelo_usado). Lanza ErrorIA si todos los modelos fallan."""
    clave = os.getenv("GEMINI_API_KEY", "").strip()
    modelos = _modelos()
    if not clave or not modelos:
        raise ErrorIA("Falta GEMINI_API_KEY o GEMINI_MODEL en el .env")

    cuerpo = {
        "systemInstruction": {"parts": [{"text": sistema}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0},
    }
    if como_json:
        cuerpo["generationConfig"]["responseMimeType"] = "application/json"

    fallos = []
    for modelo in modelos:
        for intento in range(intentos):
            try:
                r = httpx.post(f"{BASE}/models/{modelo}:generateContent", json=cuerpo,
                               headers={"x-goog-api-key": clave}, timeout=40)
            except httpx.HTTPError as e:
                fallos.append(f"{modelo}: {type(e).__name__}")
            else:
                if r.status_code == 200:
                    return _texto(r.json()), modelo
                fallos.append(f"{modelo}: HTTP {r.status_code}")
                if r.status_code not in REINTENTABLES:
                    break              # error de configuración: reintentar no sirve, pasar al respaldo
            if intento < intentos - 1:
                time.sleep(espera)
    raise ErrorIA("No respondió ningún modelo (" + "; ".join(fallos) + ")")
