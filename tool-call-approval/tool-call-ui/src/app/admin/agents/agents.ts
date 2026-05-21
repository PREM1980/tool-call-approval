import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AgentsService } from '../../services/agents.service';
import { DeployForm } from './deploy-form/deploy-form';
import { AgentList } from './agent-list/agent-list';
import { AgentConfigure } from './agent-configure/agent-configure';

@Component({
  selector: 'app-agents',
  standalone: true,
  imports: [CommonModule, DeployForm, AgentList, AgentConfigure],
  templateUrl: './agents.html',
  styleUrl: './agents.css',
})
export class Agents implements OnInit {
  tab: 'deployments' | 'view' | 'configure' = 'deployments';
  kubeconfigError = '';

  constructor(private agentsService: AgentsService) {}

  async ngOnInit() {
    try {
      await this.agentsService.syncKubeconfig();
    } catch {
      this.kubeconfigError = 'Kubeconfig not configured. Save credentials first.';
    }
  }

  onDeployed() {
    this.tab = 'view';
  }
}
