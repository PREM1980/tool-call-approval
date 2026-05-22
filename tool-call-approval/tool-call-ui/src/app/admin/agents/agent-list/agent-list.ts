import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentsService, AgentDeployment } from '../../../services/agents.service';

@Component({
  selector: 'app-agent-list',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './agent-list.html',
  styleUrl: './agent-list.css',
})
export class AgentList implements OnInit, OnDestroy {
  agents: AgentDeployment[] = [];
  loading = true;
  error = '';
  private _poll: ReturnType<typeof setInterval> | null = null;

  constructor(private agentsService: AgentsService) {}

  ngOnInit() {
    this.load();
    this._poll = setInterval(() => this.load(), 10_000);
  }

  ngOnDestroy() {
    if (this._poll) clearInterval(this._poll);
  }

  async load() {
    try {
      this.agents = await this.agentsService.list();
      this.error = '';
    } catch (e: any) {
      this.error = e?.error?.detail ?? 'Failed to load agents';
    } finally {
      this.loading = false;
    }
  }

  async scale(agent: AgentDeployment, delta: number) {
    const next = Math.max(0, agent.replicas + delta);
    try {
      await this.agentsService.scale(agent.name, agent.namespace, next);
      agent.replicas = next;
    } catch (e: any) {
      alert(e?.error?.detail ?? 'Scale failed');
    }
  }

  async restart(agent: AgentDeployment) {
    const prev = agent.status;
    agent.status = 'Restarting';
    try {
      await this.agentsService.restart(agent.name, agent.namespace);
      setTimeout(() => this.load(), 3000);
    } catch (e: any) {
      agent.status = prev;
      alert(e?.error?.detail ?? 'Restart failed');
    }
  }

  async delete(agent: AgentDeployment) {
    if (!confirm(`Delete ${agent.name}?`)) return;
    try {
      await this.agentsService.delete(agent.name, agent.namespace);
      this.agents = this.agents.filter(a => a.name !== agent.name);
    } catch (e: any) {
      alert(e?.error?.detail ?? 'Delete failed');
    }
  }
}
