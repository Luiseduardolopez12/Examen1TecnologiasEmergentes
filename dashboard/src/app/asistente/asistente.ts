import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, Injectable, inject, signal, viewChild } from '@angular/core';
import { Api, FuenteAsistente } from '../nucleo/api';

export interface Mensaje {
  rol: 'usuario' | 'asistente' | 'error';
  texto: string;
  respondida?: boolean;
  fuentes?: FuenteAsistente[];
  segundos?: number;
}

/** Guarda la conversación para que no se pierda al cambiar de pestaña. */
@Injectable({ providedIn: 'root' })
export class Conversacion {
  mensajes = signal<Mensaje[]>([]);
}

const NOMBRES: Record<string, string> = {
  kpis: 'Indicadores generales',
  ventas_mensuales: 'Ventas por mes',
  top_productos: 'Top productos',
  top_clientes: 'Top clientes',
  ventas_por_territorio: 'Ventas por territorio',
  ventas_por_grupo: 'Ventas por grupo de producto',
  vendedores: 'Ventas por vendedor',
  pronostico: 'Predicción de ventas',
};

@Component({
  selector: 'app-asistente',
  templateUrl: './asistente.html',
  styleUrl: './asistente.css',
})
export class Asistente {
  private api = inject(Api);
  private conversacion = inject(Conversacion);
  private lista = viewChild<ElementRef<HTMLElement>>('lista');

  mensajes = this.conversacion.mensajes;
  texto = signal('');
  pensando = signal(false);

  ejemplos = [
    '¿Cuánto hemos vendido en total y cuál es el margen?',
    '¿Cuáles son los 5 productos más vendidos?',
    'Compara las ventas de 2014 contra 2015',
    '¿Qué territorio vende más?',
    '¿Cuánto vamos a vender en los próximos meses?',
  ];

  constructor() { setTimeout(() => this.bajar()); }

  enviar(pregunta = this.texto()) {
    pregunta = pregunta.trim();
    if (pregunta.length < 3 || this.pensando()) return;
    this.texto.set('');
    this.agregar({ rol: 'usuario', texto: pregunta });
    this.pensando.set(true);
    this.api.preguntar(pregunta).subscribe({
      next: r => {
        this.pensando.set(false);
        this.agregar({ rol: 'asistente', texto: r.respuesta, respondida: r.respondida,
                       fuentes: r.fuentes, segundos: Math.round(r.duracion_ms / 100) / 10 });
      },
      error: (e: HttpErrorResponse) => {
        this.pensando.set(false);
        const detalle = typeof e.error?.detail === 'string' ? e.error.detail : '';
        this.agregar({ rol: 'error', texto: detalle ||
          (e.status === 0 ? 'No se pudo conectar con la API. ¿Está encendida?' : 'No se pudo obtener respuesta.') });
      },
    });
  }

  teclado(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.enviar(); }
  }

  limpiar() { this.mensajes.set([]); }

  nombre(herramienta: string) { return NOMBRES[herramienta] ?? herramienta; }

  filtros(f: Record<string, string>): string {
    return Object.entries(f).map(([k, v]) => `${k} ${v}`).join(' · ');
  }

  /** Separa **negritas** en partes para mostrarlas sin usar innerHTML. */
  lineas(texto: string) {
    return texto.split('\n').map(l =>
      l.split('**').map((parte, i) => ({ texto: parte, negrita: i % 2 === 1 })).filter(p => p.texto));
  }

  private agregar(m: Mensaje) {
    this.mensajes.update(l => [...l, m]);
    setTimeout(() => this.bajar());
  }

  private bajar() {
    const el = this.lista()?.nativeElement;
    if (el) el.scrollTop = el.scrollHeight;
  }
}
