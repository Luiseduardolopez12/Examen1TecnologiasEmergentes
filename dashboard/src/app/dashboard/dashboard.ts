import { Component, OnDestroy, computed, inject, signal } from '@angular/core';
import { Subscription, forkJoin } from 'rxjs';
import {
  Api, Cliente, Detalle, Filtros, Grupo, Kpis, Mes, Opciones, Producto, Territorio, Vendedor,
} from '../nucleo/api';
import { dinero, dinero2, fecha, numero, porcentaje } from '../nucleo/formato';
import { Grafico } from '../grafico/grafico';

@Component({
  selector: 'app-dashboard',
  imports: [Grafico],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnDestroy {
  private api = inject(Api);

  // formatos disponibles en la plantilla
  dinero = dinero; dinero2 = dinero2; numero = numero; porcentaje = porcentaje; fecha = fecha;

  filtros = signal<Filtros>({});
  opciones = signal<Opciones | null>(null);
  kpis = signal<Kpis | null>(null);
  mensual = signal<Mes[]>([]);
  productos = signal<Producto[]>([]);
  clientes = signal<Cliente[]>([]);
  territorios = signal<Territorio[]>([]);
  grupos = signal<Grupo[]>([]);
  vendedores = signal<Vendedor[]>([]);
  detalle = signal<Detalle | null>(null);
  pagina = signal(1);

  cargando = signal(true);
  error = signal('');
  avisoFechas = signal('');

  // datos listos para los gráficos
  mesesEtiquetas = computed(() => this.mensual().map(m => m.mes));
  mesesSeries = computed(() => [
    { nombre: 'Ventas netas', valores: this.mensual().map(m => m.ventas_netas) },
    { nombre: 'Ganancia', valores: this.mensual().map(m => m.ganancia) },
  ]);
  productosEtiquetas = computed(() => this.productos().map(p => p.producto));
  productosSeries = computed(() => [{ nombre: 'Ventas netas', valores: this.productos().map(p => p.ventas_netas) }]);
  territoriosEtiquetas = computed(() => this.territorios().map(t => t.territorio));
  territoriosSeries = computed(() => [{ nombre: 'Ventas netas', valores: this.territorios().map(t => t.ventas_netas) }]);
  gruposEtiquetas = computed(() => this.grupos().map(g => g.grupo));
  gruposSeries = computed(() => [{ nombre: 'Ventas netas', valores: this.grupos().map(g => g.ventas_netas) }]);
  vendedoresEtiquetas = computed(() => this.vendedores().map(v => v.vendedor));
  vendedoresSeries = computed(() => [{ nombre: 'Ventas netas', valores: this.vendedores().map(v => v.ventas_netas) }]);

  totalPaginas = computed(() => {
    const d = this.detalle();
    return d ? Math.max(1, Math.ceil(d.total / d.tamano)) : 1;
  });
  hayFiltros = computed(() => Object.values(this.filtros()).some(v => !!v));

  private subGeneral?: Subscription;
  private subDetalle?: Subscription;

  constructor() {
    this.api.opciones().subscribe({ next: o => this.opciones.set(o), error: () => {} });
    this.recargar();
  }

  ngOnDestroy() {
    this.subGeneral?.unsubscribe();
    this.subDetalle?.unsubscribe();
  }

  cambiar(campo: keyof Filtros, valor: string) {
    this.filtros.update(f => ({ ...f, [campo]: valor }));
    this.pagina.set(1);
    this.recargar();
  }

  limpiar() {
    this.filtros.set({});
    this.pagina.set(1);
    this.recargar();
  }

  irAPagina(n: number) {
    if (n < 1 || n > this.totalPaginas()) return;
    this.pagina.set(n);
    this.cargarDetalle();
  }

  private recargar() {
    const f = this.filtros();
    // validamos antes de molestar a la API
    if (f.desde && f.hasta && f.desde > f.hasta) {
      this.avisoFechas.set('La fecha "Desde" no puede ser posterior a "Hasta".');
      return;
    }
    this.avisoFechas.set('');
    this.cargando.set(true);
    this.error.set('');
    this.subGeneral?.unsubscribe();
    // si el usuario cambia otro filtro a mitad de la carga, la petición vieja se cancela
    this.subGeneral = forkJoin({
      kpis: this.api.kpis(f),
      mensual: this.api.mensual(f),
      productos: this.api.productos(f),
      clientes: this.api.clientes(f),
      territorios: this.api.territorios(f),
      grupos: this.api.grupos(f),
      vendedores: this.api.vendedores(f),
    }).subscribe({
      next: r => {
        this.kpis.set(r.kpis);
        this.mensual.set(r.mensual);
        this.productos.set(r.productos);
        this.clientes.set(r.clientes);
        this.territorios.set(r.territorios);
        this.grupos.set(r.grupos);
        this.vendedores.set(r.vendedores);
        this.cargando.set(false);
      },
      error: () => {
        this.cargando.set(false);
        this.error.set('No se pudieron cargar los datos. Revisa que la API esté encendida.');
      },
    });
    this.cargarDetalle();
  }

  private cargarDetalle() {
    this.subDetalle?.unsubscribe();
    this.subDetalle = this.api.detalle(this.filtros(), this.pagina()).subscribe({
      next: d => this.detalle.set(d),
      error: () => {},
    });
  }
}
