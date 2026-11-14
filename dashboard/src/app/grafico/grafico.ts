import { Component, ElementRef, OnDestroy, effect, input, signal, viewChild } from '@angular/core';
import { Chart, registerables } from 'chart.js';
import { dinero, dineroCompacto } from '../nucleo/formato';

Chart.register(...registerables);

export interface Serie { nombre: string; valores: number[]; }

/** Gráfico de líneas o de barras (horizontales o verticales) con Chart.js.
 *  Los colores salen de las variables CSS, así que cambia solo con el modo claro/oscuro. */
@Component({
  selector: 'app-grafico',
  template: `<canvas #lienzo role="img" [attr.aria-label]="descripcion()"></canvas>`,
  styles: [`:host { display: block; position: relative; width: 100%; height: 100%; }`],
})
export class Grafico implements OnDestroy {
  tipo = input<'linea' | 'barras'>('barras');
  horizontal = input(false);
  etiquetas = input.required<string[]>();
  series = input.required<Serie[]>();
  descripcion = input('');

  private lienzo = viewChild<ElementRef<HTMLCanvasElement>>('lienzo');
  private grafico?: Chart;
  private tema = signal(0);
  private oscuro = matchMedia('(prefers-color-scheme: dark)');
  private alCambiarTema = () => this.tema.update(v => v + 1);

  constructor() {
    this.oscuro.addEventListener('change', this.alCambiarTema);
    effect(() => {
      this.tema();
      this.dibujar();
    });
  }

  ngOnDestroy() {
    this.oscuro.removeEventListener('change', this.alCambiarTema);
    this.grafico?.destroy();
  }

  private color(nombre: string) {
    return getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
  }

  private dibujar() {
    const lienzo = this.lienzo()?.nativeElement;
    const etiquetas = this.etiquetas();
    const series = this.series();
    const esLinea = this.tipo() === 'linea';
    const horizontal = this.horizontal() && !esLinea;
    if (!lienzo) return;
    this.grafico?.destroy();

    const colores = [this.color('--serie-1'), this.color('--serie-2')];
    const texto2 = this.color('--texto-2');
    const texto3 = this.color('--texto-3');
    const rejilla = this.color('--rejilla');
    const superficie = this.color('--superficie');

    const datasets = series.map((s, i) => ({
      label: s.nombre,
      data: s.valores,
      borderColor: colores[i],
      backgroundColor: esLinea ? colores[i] : colores[i],
      borderWidth: esLinea ? 2 : 0,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHoverBackgroundColor: colores[i],
      pointHoverBorderColor: superficie,
      pointHoverBorderWidth: 2,
      tension: 0,   // líneas rectas: no inventamos curvas entre meses
      maxBarThickness: 20,
      // esquinas redondeadas solo en el extremo del dato, pegado a la base
      borderRadius: horizontal ? { topRight: 4, bottomRight: 4 } : { topLeft: 4, topRight: 4 },
      borderSkipped: false,
    }));

    const ejeValor = {
      grid: { color: rejilla },
      border: { display: false },
      ticks: { color: texto3, callback: (v: number | string) => dineroCompacto(Number(v)) },
      beginAtZero: true,
    };
    const ejeCategoria = {
      grid: { display: false },
      border: { color: rejilla },
      ticks: {
        color: texto2,
        maxRotation: 0,
        autoSkip: esLinea,
        maxTicksLimit: esLinea ? 10 : undefined,
        callback(this: any, valor: number | string) {
          const t = String(this.getLabelForValue(valor as number));
          return t.length > 26 ? t.slice(0, 25) + '…' : t;
        },
      },
    };

    this.grafico = new Chart(lienzo, {
      type: esLinea ? 'line' : 'bar',
      data: { labels: etiquetas, datasets: datasets as any },
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 250 },
        interaction: { mode: esLinea ? 'index' : 'nearest', intersect: !esLinea, axis: horizontal ? 'y' : 'x' },
        plugins: {
          legend: {
            display: series.length > 1,
            align: 'start',
            labels: { color: texto2, usePointStyle: true, pointStyle: 'rectRounded', boxWidth: 10, padding: 16 },
          },
          tooltip: {
            backgroundColor: superficie,
            titleColor: this.color('--texto'),
            bodyColor: texto2,
            borderColor: this.color('--borde'),
            borderWidth: 1,
            padding: 10,
            callbacks: {
              label: (c: any) => ` ${c.dataset.label}: ${dinero(horizontal ? c.parsed.x : c.parsed.y)}`,
            },
          },
        },
        scales: horizontal
          ? { x: ejeValor as any, y: ejeCategoria as any }
          : { x: ejeCategoria as any, y: ejeValor as any },
      },
    });
  }
}
