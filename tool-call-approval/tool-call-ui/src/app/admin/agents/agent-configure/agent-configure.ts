import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService, AgentInstance, PersonaData, McpServer } from '../../../services/admin.service';
import { AgentsService, AgentDeployment } from '../../../services/agents.service';

interface InstanceForm {
  id: string | null;
  instance_name: string;
  persona_id: string | null;
  mcp_positions: number[];
  expanded: boolean;
  saving: boolean;
  error: string;
}

@Component({
  selector: 'app-agent-configure',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './agent-configure.html',
  styleUrl: './agent-configure.css',
})
export class AgentConfigure implements OnInit {
  agents: AgentDeployment[] = [];
  personas: PersonaData[] = [];
  mcpServers: McpServer[] = [];
  instances: InstanceForm[] = [];
  selectedAgent = '';
  loading = false;
  error = '';

  constructor(
    private adminService: AdminService,
    private agentsService: AgentsService,
  ) {}

  async ngOnInit() {
    const [agents, personas, mcpServers] = await Promise.all([
      this.agentsService.list(),
      this.adminService.getPersonas(),
      this.adminService.getMcpServers(),
    ]);
    this.agents = agents;
    this.personas = personas;
    this.mcpServers = mcpServers;
    if (agents.length > 0) {
      this.selectedAgent = agents[0].name;
      await this.loadInstances();
    }
  }

  async onAgentChange() {
    await this.loadInstances();
  }

  async loadInstances() {
    if (!this.selectedAgent) return;
    this.loading = true;
    try {
      const raw = await this.adminService.getAgentInstances(this.selectedAgent);
      this.instances = raw.map(i => this._toForm(i));
      this.error = '';
    } catch {
      this.error = 'Failed to load instances';
    } finally {
      this.loading = false;
    }
  }

  addInstance() {
    this.instances.push({
      id: null,
      instance_name: '',
      persona_id: null,
      mcp_positions: [],
      expanded: true,
      saving: false,
      error: '',
    });
  }

  toggle(form: InstanceForm) {
    form.expanded = !form.expanded;
  }

  isMcpSelected(form: InstanceForm, position: number): boolean {
    return form.mcp_positions.includes(position);
  }

  toggleMcp(form: InstanceForm, position: number) {
    const idx = form.mcp_positions.indexOf(position);
    if (idx >= 0) {
      form.mcp_positions.splice(idx, 1);
    } else {
      form.mcp_positions.push(position);
    }
  }

  async save(form: InstanceForm) {
    if (!form.instance_name.trim()) {
      form.error = 'Instance name is required';
      return;
    }
    form.saving = true;
    form.error = '';
    try {
      let saved: AgentInstance;
      if (form.id === null) {
        saved = await this.adminService.createAgentInstance(
          this.selectedAgent,
          form.instance_name,
          form.persona_id,
          form.mcp_positions,
        );
      } else {
        saved = await this.adminService.updateAgentInstance(
          form.id,
          form.instance_name,
          form.persona_id,
          form.mcp_positions,
        );
      }
      Object.assign(form, this._toForm(saved));
    } catch (e: any) {
      form.error = e?.error?.detail ?? 'Save failed';
    } finally {
      form.saving = false;
    }
  }

  async deleteInstance(form: InstanceForm, index: number) {
    if (!confirm(`Delete instance "${form.instance_name}"?`)) return;
    if (form.id !== null) {
      try {
        await this.adminService.deleteAgentInstance(form.id);
      } catch (e: any) {
        form.error = e?.error?.detail ?? 'Delete failed';
        return;
      }
    }
    this.instances.splice(index, 1);
  }

  personaName(id: string | null): string {
    if (!id) return '—';
    return this.personas.find(p => p.id === id)?.name ?? '—';
  }

  mcpSummary(positions: number[]): string {
    if (positions.length === 0) return '—';
    return positions
      .map(p => this.mcpServers.find(s => s.position === p)?.name ?? `#${p}`)
      .join(', ');
  }

  private _toForm(i: AgentInstance): InstanceForm {
    return {
      id: i.id,
      instance_name: i.instance_name,
      persona_id: i.persona_id,
      mcp_positions: [...i.mcp_positions],
      expanded: false,
      saving: false,
      error: '',
    };
  }
}
