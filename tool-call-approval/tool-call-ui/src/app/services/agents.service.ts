import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { AdminService } from './admin.service';

const API = 'http://localhost:8080/api';

export interface EnvVar {
  key: string;
  value: string;
}

export interface DeployRequest {
  name: string;
  image: string;
  namespace: string;
  replicas: number;
  env: EnvVar[];
}

export interface AgentDeployment {
  name: string;
  namespace: string;
  image: string;
  replicas: number;
  ready_replicas: number;
  status: string;
}

@Injectable({ providedIn: 'root' })
export class AgentsService {
  constructor(private http: HttpClient, private adminService: AdminService) {}

  async syncKubeconfig(): Promise<void> {
    const creds = await this.adminService.getCredentials();
    if (creds?.kubeconfig) {
      await firstValueFrom(
        this.http.post(`${API}/k8s-config`, { content: creds.kubeconfig })
      );
    }
  }

  deploy(req: DeployRequest) {
    return firstValueFrom(this.http.post<AgentDeployment>(`${API}/agents`, req));
  }

  list() {
    return firstValueFrom(this.http.get<AgentDeployment[]>(`${API}/agents`));
  }

  delete(name: string, namespace: string) {
    return firstValueFrom(
      this.http.delete(`${API}/agents/${name}?namespace=${namespace}`)
    );
  }

  restart(name: string, namespace: string) {
    return firstValueFrom(
      this.http.post(`${API}/agents/${name}/restart?namespace=${namespace}`, {})
    );
  }

  scale(name: string, namespace: string, replicas: number) {
    return firstValueFrom(
      this.http.patch(`${API}/agents/${name}/scale?namespace=${namespace}`, { replicas })
    );
  }
}
