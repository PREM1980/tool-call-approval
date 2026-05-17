import { Routes } from '@angular/router';
import { AppShell } from './app-shell/app-shell';

export const routes: Routes = [
  {
    path: '',
    component: AppShell,
    children: [
      { path: '', redirectTo: 'ai-engg', pathMatch: 'full' },
      {
        path: 'ai-engg',
        loadComponent: () =>
          import('./components/chat/chat').then((m) => m.Chat),
      },
      {
        path: 'admin',
        loadComponent: () =>
          import('./admin/admin-layout/admin-layout').then((m) => m.AdminLayout),
        loadChildren: () =>
          import('./admin/admin.routes').then((m) => m.adminRoutes),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
