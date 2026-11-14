import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { Sesion } from './sesion';

/** Agrega el token a cada petición y, si la API dice 401, cierra la sesión. */
export const interceptorToken: HttpInterceptorFn = (req, next) => {
  const sesion = inject(Sesion);
  const router = inject(Router);
  const esLogin = req.url.endsWith('/auth/login');

  if (sesion.activa && !esLogin) {
    req = req.clone({ setHeaders: { Authorization: `Bearer ${sesion.token}` } });
  }
  return next(req).pipe(
    catchError((e: HttpErrorResponse) => {
      if (e.status === 401 && !esLogin) {
        sesion.cerrar();
        router.navigate(['/login']);
      }
      return throwError(() => e);
    }),
  );
};
