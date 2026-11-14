import { Injectable, inject, signal } from '@angular/core';
import { Api } from './api';

/** Cuántas alertas nuevas hay; lo usan el menú, el aviso y la página de alertas. */
@Injectable({ providedIn: 'root' })
export class EstadoAlertas {
  private api = inject(Api);
  nuevas = signal(0);

  refrescar() {
    this.api.alertas().subscribe({
      next: lista => this.nuevas.set(lista.filter(a => a.estado === 'NUEVA').length),
      error: () => {},
    });
  }
}
