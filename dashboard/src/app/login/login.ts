import { Component, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Api } from '../nucleo/api';
import { Sesion } from '../nucleo/sesion';

@Component({
  selector: 'app-login',
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  private api = inject(Api);
  private sesion = inject(Sesion);
  private router = inject(Router);

  usuario = signal('');
  clave = signal('');
  error = signal('');
  entrando = signal(false);

  entrar(evento: Event) {
    evento.preventDefault();
    if (!this.usuario() || !this.clave()) {
      this.error.set('Escribe tu usuario y tu clave.');
      return;
    }
    this.error.set('');
    this.entrando.set(true);
    this.api.login(this.usuario(), this.clave()).subscribe({
      next: r => {
        this.sesion.guardar(r.token);
        this.router.navigate(['/']);
      },
      error: e => {
        this.entrando.set(false);
        this.error.set(e.status === 401
          ? 'Usuario o clave incorrectos.'
          : 'No se pudo conectar con la API. ¿Está encendida en el puerto 8000?');
      },
    });
  }
}
