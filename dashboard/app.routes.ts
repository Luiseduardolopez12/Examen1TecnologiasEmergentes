import { Routes } from '@angular/router';
import { guardiaSesion } from './nucleo/guardia';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./login/login').then(m => m.Login) },
  {
    path: '',
    canActivate: [guardiaSesion],
    loadComponent: () => import('./layout/layout').then(m => m.Layout),
    children: [
      { path: '', loadComponent: () => import('./dashboard/dashboard').then(m => m.Dashboard) },
      { path: 'asistente', loadComponent: () => import('./asistente/asistente').then(m => m.Asistente) },
      { path: 'alertas', loadComponent: () => import('./alertas/alertas').then(m => m.Alertas) },
      { path: 'etl', loadComponent: () => import('./etl/etl').then(m => m.Etl) },
    ],
  },
  { path: '**', redirectTo: '' },
];
