"Login simple: usuario y clave del .env, token firmado con expiración (solo librería estándar)."
import base64
import hashlib
import hmac
import json
import os
import time

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

DURACION_SEGUNDOS = 8 * 3600

# Esto es lo que hace que Swagger (/docs) muestre el botón Authorize
esquema = HTTPBearer(auto_error=False)


def _config():
    usuario = os.getenv("API_USER")
    clave = os.getenv("API_PASSWORD")
    secreto = os.getenv("API_SECRET")
    if not (usuario and clave and secreto):
        raise RuntimeError("Faltan API_USER, API_PASSWORD o API_SECRET en el .env")
    return usuario, clave, secreto


def _firma(cuerpo, secreto):
    return hmac.new(secreto.encode(), cuerpo.encode(), hashlib.sha256).hexdigest()


def crear_token(usuario):
    _, _, secreto = _config()
    datos = {"u": usuario, "exp": int(time.time()) + DURACION_SEGUNDOS}
    cuerpo = base64.urlsafe_b64encode(json.dumps(datos).encode()).decode()
    return f"{cuerpo}.{_firma(cuerpo, secreto)}"


def validar_credenciales(usuario, clave):
    u, c, _ = _config()
    # compare_digest evita adivinar la clave midiendo tiempos de respuesta
    return hmac.compare_digest(usuario, u) and hmac.compare_digest(clave, c)


def usuario_actual(credenciales: HTTPAuthorizationCredentials = Depends(esquema)):
    """Dependencia: exige 'Authorization: Bearer <token>' válido y vigente."""
    _, _, secreto = _config()
    if credenciales is None:
        raise HTTPException(401, "Falta el token")
    # Perdona errores comunes al pegar: espacios, comillas o un "Bearer" repetido
    token = credenciales.credentials.strip().strip('"').strip("'")
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    try:
        cuerpo, firma = token.split(".")
        if not hmac.compare_digest(firma, _firma(cuerpo, secreto)):
            raise ValueError
        datos = json.loads(base64.urlsafe_b64decode(cuerpo))
        if datos["exp"] < time.time():
            raise HTTPException(401, "El token expiró, inicia sesión otra vez")
        return datos["u"]
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(401, "Token inválido")