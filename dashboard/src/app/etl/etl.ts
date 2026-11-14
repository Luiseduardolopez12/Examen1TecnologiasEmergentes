import { Component, computed, inject, signal } from '@angular/core';
import { Api, Ejecucion } from '../nucleo/api';
import { fecha, numero } from '../nucleo/formato';

@Component({
  selector: 'app-etl',
  templateUrl: './etl.html',
  styleUrl: './etl.css',
})
export class Etl {
  private api = inject(Api);
  fecha = fecha; numero = numero;

  ejecuciones = signal<Ejecucion[]>([]);
  error = signal('');
  cargando = signal(true);

  fallidas = computed(() => this.ejecuciones().filter(e => e.status === 'FAILED').length);
  ultima = computed(() => this.ejecuciones()[0] ?? null);
  rechazadas = computed(() => this.ejecuciones().reduce((s, e) => s + (e.rows_rejected ?? 0), 0));

  constructor() { this.cargar(); }

  cargar() {
    this.cargando.set(true);
    this.api.ejecuciones().subscribe({
      next: e => { this.ejecuciones.set(e); this.cargando.set(false); this.error.set(''); },
      error: () => { this.cargando.set(false); this.error.set('No se pudo leer el historial del ETL.'); },
    });
  }

  duracion(e: Ejecucion): string {
    if (!e.end_time) return '—';
    const seg = (new Date(e.end_time).getTime() - new Date(e.start_time).getTime()) / 1000;
    return seg < 60 ? `${seg.toFixed(1)} s` : `${Math.floor(seg / 60)} min ${Math.round(seg % 60)} s`;
  }
}
