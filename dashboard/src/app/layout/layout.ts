import { Component, inject, signal } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { Actualizacion, Api } from '../nucleo/api';
import { fecha } from '../nucleo/formato';
import { Sesion } from '../nucleo/sesion';

@Component({
  selector: 'app-layout',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './layout.html',
  styleUrl: './layout.css',
})
export class Layout {
  private api = inject(Api);
  private sesion = inject(Sesion);
  private router = inject(Router);

  fecha = fecha;
  actualizacion = signal<Actualizacion | null>(null);

  constructor() {
    this.api.actualizacion().subscribe({ next: a => this.actualizacion.set(a), error: () => {} });
  }

  salir() {
    this.sesion.cerrar();
    this.router.navigate(['/login']);
  }
}
