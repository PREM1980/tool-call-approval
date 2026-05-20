import { Routes } from '@angular/router';

export const adminRoutes: Routes = [
  { path: '', redirectTo: 'agent-ws', pathMatch: 'full' },
  {
    path: 'agent-ws',
    loadComponent: () =>
      import('./agent-ws/agent-ws').then((m) => m.AgentWs),
  },
  {
    path: 'credentials',
    loadComponent: () =>
      import('./credentials/credentials').then((m) => m.Credentials),
  },
  {
    path: 'mcp-servers',
    loadComponent: () =>
      import('./mcp-servers/mcp-servers').then((m) => m.McpServers),
  },
  {
    path: 'skills',
    loadComponent: () =>
      import('./skills/skills').then((m) => m.Skills),
  },
  {
    path: 'persona',
    loadComponent: () =>
      import('./persona/persona').then((m) => m.Persona),
  },
  {
    path: 'agents',
    loadComponent: () =>
      import('./agents/agents').then((m) => m.Agents),
  },
];
