import { Injectable } from '@angular/core';

const CLAVE = 'token_ventas';

/** Guarda el token mientras la pestaña esté abierta. Si el navegador no deja usar
 *  sessionStorage, se queda en memoria y la página sigue funcionando. */
@Injectable({ providedIn: 'root' })
export class Sesion {
  private enMemoria = '';

  get token(): string {
    try {
      return sessionStorage.getItem(CLAVE) ?? this.enMemoria;
    } catch {
      return this.enMemoria;
    }
  }

  guardar(token: string) {
    this.enMemoria = token;
    try { sessionStorage.setItem(CLAVE, token); } catch { /* sin almacenamiento */ }
  }

  cerrar() {
    this.enMemoria = '';
    try { sessionStorage.removeItem(CLAVE); } catch { /* sin almacenamiento */ }
  }

  get activa(): boolean {
    return this.token !== '';
  }
}
