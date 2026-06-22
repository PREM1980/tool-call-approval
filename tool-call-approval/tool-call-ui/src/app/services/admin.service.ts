import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

const API = '/api/admin';

export interface CredentialsData {
  aws_access_key_id: string;
  aws_secret_access_key: string;
  aws_region: string;
  kubeconfig: string | null;
}

export interface McpServer {
  position: number;
  name: string;
  config: Record<string, unknown>;
  updated_at: string;
}

export interface Skill {
  id: string;
  filename: string;
  uploaded_at: string;
}

export interface PersonaData {
  id: string;
  name: string;
  skill_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface AgentInstance {
  id: string;
  agent_name: string;
  instance_name: string;
  persona_id: string | null;
  mcp_positions: number[];
  created_at: string;
  updated_at: string;
}

export interface SystemPromptData {
  id: string;
  name: string;
  instructions: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AppUser {
  id: string;
  username: string;
  role: 'admin' | 'user';
}

@Injectable({ providedIn: 'root' })
export class AdminService {
  constructor(private http: HttpClient) {}

  getCredentials() {
    return firstValueFrom(this.http.get<CredentialsData | null>(`${API}/credentials`));
  }

  saveCredentials(creds: CredentialsData) {
    return firstValueFrom(this.http.post(`${API}/credentials`, creds));
  }

  getMcpServers() {
    return firstValueFrom(this.http.get<McpServer[]>(`${API}/mcp-servers`));
  }

  saveMcpServer(position: number, name: string, config: Record<string, unknown>) {
    return firstValueFrom(this.http.post(`${API}/mcp-servers/${position}`, { name, config }));
  }

  deleteMcpServer(position: number) {
    return firstValueFrom(this.http.delete(`${API}/mcp-servers/${position}`));
  }

  getSkills() {
    return firstValueFrom(this.http.get<Skill[]>(`${API}/skills`));
  }

  uploadSkill(file: File) {
    const form = new FormData();
    form.append('file', file);
    return firstValueFrom(this.http.post<Skill>(`${API}/skills`, form));
  }

  deleteSkill(id: string) {
    return firstValueFrom(this.http.delete(`${API}/skills/${id}`));
  }

  getPersonas() {
    return firstValueFrom(this.http.get<PersonaData[]>(`${API}/personas`));
  }

  createPersona(name: string, skill_ids: string[]) {
    return firstValueFrom(this.http.post<PersonaData>(`${API}/personas`, { name, skill_ids }));
  }

  updatePersona(id: string, name: string, skill_ids: string[]) {
    return firstValueFrom(this.http.put<PersonaData>(`${API}/personas/${id}`, { name, skill_ids }));
  }

  deletePersona(id: string) {
    return firstValueFrom(this.http.delete(`${API}/personas/${id}`));
  }

  getAgentInstances(agentName: string) {
    return firstValueFrom(
      this.http.get<AgentInstance[]>(
        `${API}/agent-instances?agent_name=${encodeURIComponent(agentName)}`
      )
    );
  }

  getAllAgentInstances() {
    return firstValueFrom(this.http.get<AgentInstance[]>(`${API}/agent-instances`));
  }

  createAgentInstance(
    agentName: string,
    instanceName: string,
    personaId: string | null,
    mcpPositions: number[]
  ) {
    return firstValueFrom(
      this.http.post<AgentInstance>(`${API}/agent-instances`, {
        agent_name: agentName,
        instance_name: instanceName,
        persona_id: personaId,
        mcp_positions: mcpPositions,
      })
    );
  }

  updateAgentInstance(
    id: string,
    instanceName: string,
    personaId: string | null,
    mcpPositions: number[]
  ) {
    return firstValueFrom(
      this.http.put<AgentInstance>(`${API}/agent-instances/${id}`, {
        instance_name: instanceName,
        persona_id: personaId,
        mcp_positions: mcpPositions,
      })
    );
  }

  deleteAgentInstance(id: string) {
    return firstValueFrom(this.http.delete(`${API}/agent-instances/${id}`));
  }

  listSystemPrompts() {
    return firstValueFrom(this.http.get<SystemPromptData[]>(`${API}/system-prompts`));
  }

  createSystemPrompt(name: string, instructions: string) {
    return firstValueFrom(this.http.post<SystemPromptData>(`${API}/system-prompts`, { name, instructions }));
  }

  updateSystemPrompt(id: string, name: string, instructions: string) {
    return firstValueFrom(this.http.put<SystemPromptData>(`${API}/system-prompts/${id}`, { name, instructions }));
  }

  deleteSystemPrompt(id: string) {
    return firstValueFrom(this.http.delete(`${API}/system-prompts/${id}`));
  }

  activateSystemPrompt(id: string) {
    return firstValueFrom(this.http.post<SystemPromptData>(`${API}/system-prompts/${id}/activate`, {}));
  }

  listUsers() {
    return firstValueFrom(this.http.get<AppUser[]>(`${API}/users`));
  }

  createUser(username: string, password: string, role: 'admin' | 'user') {
    return firstValueFrom(this.http.post<AppUser>(`${API}/users`, { username, password, role }));
  }
}
