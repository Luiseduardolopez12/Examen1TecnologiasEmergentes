import { Component, computed, inject, signal } from '@angular/core';
import { Alerta, Api } from '../nucleo/api';
import { EstadoAlertas } from '../nucleo/estado-alertas';
import { dinero, fecha } from '../nucleo/formato';

const REGLAS: Record<string, string> = {
  caida_mensual: 'Caída vs mes anterior',
  caida_interanual: 'Caída vs mismo mes del año pasado',
};

@Component({
  selector: 'app-alertas',
  templateUrl: './alertas.html',
  styleUrl: './alertas.css',
})
export class Alertas {
  private api = inject(Api);
  private estado = inject(EstadoAlertas);
  fecha = fecha; dinero = dinero;

  lista = signal<Alerta[]>([]);
  cargando = signal(true);
  error = signal('');

  nuevas = computed(() => this.lista().filter(a => a.estado === 'NUEVA').length);
  umbral = computed(() => this.lista()[0]?.umbral_pct ?? 15);

  constructor() { this.cargar(); }

  cargar() {
    this.cargando.set(true);
    this.api.alertas().subscribe({
      next: l => { this.lista.set(l); this.cargando.set(false); this.error.set(''); this.estado.refrescar(); },
      error: () => { this.cargando.set(false); this.error.set('No se pudieron leer las alertas.'); },
    });
  }

  revisar(a: Alerta) {
    this.api.revisarAlerta(a.alerta_id).subscribe({
      next: () => {
        this.lista.update(l => l.map(x => x.alerta_id === a.alerta_id ? { ...x, estado: 'REVISADA' } : x));
        this.estado.refrescar();
      },
      error: () => this.error.set('No se pudo marcar la alerta como revisada.'),
    });
  }

  regla(r: string) { return REGLAS[r] ?? r; }
  caida(a: Alerta) { return `${a.variacion_pct.toFixed(1)} %`; }
}
