import { Component, EventEmitter, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AgentsService, EnvVar } from '../../../services/agents.service';

@Component({
  selector: 'app-deploy-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './deploy-form.html',
  styleUrl: './deploy-form.css',
})
export class DeployForm {
  @Output() deployed = new EventEmitter<void>();

  form = { name: '', image: '', namespace: 'default', replicas: 1 };
  env: EnvVar[] = [];
  deploying = false;
  error = '';

  get fullName(): string {
    return this.form.name ? `${this.form.name}-ui-agents` : '';
  }

  constructor(private agentsService: AgentsService) {}

  addEnvVar() {
    this.env.push({ key: '', value: '' });
  }

  removeEnvVar(i: number) {
    this.env.splice(i, 1);
  }

  async deploy() {
    this.deploying = true;
    this.error = '';
    try {
      await this.agentsService.deploy({
        name: this.form.name,
        image: this.form.image,
        namespace: this.form.namespace,
        replicas: this.form.replicas,
        env: this.env.filter(e => e.key.trim() !== ''),
      });
      this.deployed.emit();
    } catch (e: any) {
      this.error = e?.error?.detail ?? 'Deployment failed';
    } finally {
      this.deploying = false;
    }
  }
}
