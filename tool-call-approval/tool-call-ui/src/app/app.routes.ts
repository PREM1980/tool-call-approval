import { Routes } from '@angular/router';
import { AppShell } from './app-shell/app-shell';
import { adminGuard } from './guards/admin.guard';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./login/login').then((m) => m.Login),
  },
  {
    path: '',
    component: AppShell,
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'ai-engg', pathMatch: 'full' },
      {
        path: 'ai-engg',
        loadComponent: () =>
          import('./ai-engg/ai-engg').then((m) => m.AiEngg),
      },
      {
        path: 'admin',
        loadComponent: () =>
          import('./admin/admin-layout/admin-layout').then((m) => m.AdminLayout),
        loadChildren: () =>
          import('./admin/admin.routes').then((m) => m.adminRoutes),
      },
      {
        path: 'users',
        canActivate: [adminGuard],
        loadComponent: () =>
          import('./admin-users/admin-users').then((m) => m.AdminUsers),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
