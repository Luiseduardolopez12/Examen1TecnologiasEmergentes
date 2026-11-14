import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Sesion } from './sesion';

/** Si no hay sesión, manda al login. */
export const guardiaSesion: CanActivateFn = () => {
  const sesion = inject(Sesion);
  return sesion.activa ? true : inject(Router).createUrlTree(['/login']);
};
