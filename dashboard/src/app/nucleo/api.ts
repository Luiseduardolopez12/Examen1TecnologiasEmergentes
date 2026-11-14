import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { API_URL } from './config';

export interface Filtros { desde?: string; hasta?: string; grupo?: string; territorio?: string; }

export interface Kpis {
  ventas_netas: number; ganancia: number; unidades: number; facturas: number;
  clientes: number; margen_pct: number; ticket_promedio: number;
}
export interface Mes { mes: string; ventas_netas: number; ganancia: number; }
export interface Producto { producto: string; grupo: string; ventas_netas: number; unidades: number; }
export interface Cliente { cliente: string; ventas_netas: number; facturas: number; }
export interface Territorio { territorio: string; ventas_netas: number; }
export interface Grupo { grupo: string; ventas_netas: number; }
export interface Vendedor { vendedor: string; ventas_netas: number; ganancia: number; }
export interface LineaVenta {
  fecha: string; factura: number; cliente: string; producto: string;
  vendedor: string; cantidad: number; venta_neta: number; ganancia: number;
}
export interface Detalle { pagina: number; tamano: number; total: number; filas: LineaVenta[]; }
export interface FilaPronostico { mes: string; horizonte_mes: number; valor: number; inferior: number; superior: number; }
export interface MetricaModelo {
  modelo: string; es_baseline: boolean; ganador: boolean;
  mae_validacion: number; rmse_validacion: number; mape_validacion: number;
  mae_prueba: number; rmse_prueba: number; mape_prueba: number;
}
export interface Pronostico {
  disponible: boolean; modelo?: string; version?: string; base_hasta?: string; generado_en?: string;
  historial?: Mes[]; pronostico?: FilaPronostico[]; metricas?: MetricaModelo[];
}
export interface FuenteAsistente { herramienta: string; filtros: Record<string, string>; }
export interface RespuestaAsistente {
  respuesta: string; respondida: boolean; fuentes: FuenteAsistente[]; modelo: string; duracion_ms: number;
}
export interface Opciones { grupos: string[]; territorios: string[]; rango: { desde: string; hasta: string }; }
export interface Actualizacion { ultima_carga: string | null; datos_hasta: string | null; }
export interface Ejecucion {
  execution_id: number; pipeline_name: string; status: string; rows_read: number | null;
  rows_inserted: number | null; rows_updated: number | null; rows_rejected: number | null;
  start_time: string; end_time: string | null; error_detail: string | null;
}

@Injectable({ providedIn: 'root' })
export class Api {
  private http = inject(HttpClient);

  private params(f: Filtros, extra: Record<string, string | number> = {}) {
    let p = new HttpParams();
    for (const [k, v] of Object.entries({ ...f, ...extra })) {
      if (v !== undefined && v !== '') p = p.set(k, String(v));
    }
    return p;
  }
  private get<T>(ruta: string, f: Filtros = {}, extra: Record<string, string | number> = {}): Observable<T> {
    return this.http.get<T>(`${API_URL}${ruta}`, { params: this.params(f, extra) });
  }

  login(usuario: string, clave: string) {
    return this.http.post<{ token: string }>(`${API_URL}/auth/login`, { usuario, clave });
  }
  opciones() { return this.get<Opciones>('/api/filtros'); }
  actualizacion() { return this.get<Actualizacion>('/api/ultima-actualizacion'); }
  kpis(f: Filtros) { return this.get<Kpis>('/api/kpis', f); }
  mensual(f: Filtros) { return this.get<Mes[]>('/api/ventas-mensuales', f); }
  productos(f: Filtros) { return this.get<Producto[]>('/api/top-productos', f, { limite: 10 }); }
  clientes(f: Filtros) { return this.get<Cliente[]>('/api/top-clientes', f, { limite: 10 }); }
  territorios(f: Filtros) { return this.get<Territorio[]>('/api/ventas-por-territorio', f); }
  grupos(f: Filtros) { return this.get<Grupo[]>('/api/ventas-por-grupo', f); }
  vendedores(f: Filtros) { return this.get<Vendedor[]>('/api/vendedores', f); }
  detalle(f: Filtros, pagina: number) { return this.get<Detalle>('/api/detalle', f, { pagina, tamano: 15 }); }
  pronostico() { return this.get<Pronostico>('/api/pronostico'); }
  preguntar(pregunta: string) { return this.http.post<RespuestaAsistente>(`${API_URL}/api/asistente`, { pregunta }); }
  ejecuciones() { return this.get<Ejecucion[]>('/api/etl/ejecuciones', {}, { limite: 30 }); }
}
