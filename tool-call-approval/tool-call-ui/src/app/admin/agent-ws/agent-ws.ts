import { Component } from '@angular/core';
import { AgentConfigure } from './agent-configure/agent-configure';

@Component({
  selector: 'app-agent-ws',
  standalone: true,
  imports: [AgentConfigure],
  template: `
    <h2>Agent-WS</h2>
    <app-agent-configure />
  `,
})
export class AgentWs {}
