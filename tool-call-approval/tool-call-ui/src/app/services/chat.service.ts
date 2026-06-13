import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, firstValueFrom } from 'rxjs';
import { SseEvent } from '../models/types';

const API_URL = '/api';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private sessionId: string | null = null;
  private eventSource: EventSource | null = null;

  readonly sseEvents$ = new Subject<SseEvent>();

  constructor(private http: HttpClient) {}

  async createSession(instanceId?: string | null): Promise<void> {
    const body = instanceId ? { instance_id: instanceId } : {};
    const res = await firstValueFrom(
      this.http.post<{ session_id: string }>(`${API_URL}/sessions`, body)
    );
    this.sessionId = res.session_id;
  }

  setSession(sessionId: string): void {
    this.sessionId = sessionId;
  }

  connectStream(): void {
    if (!this.sessionId) return;
    const es = new EventSource(`${API_URL}/sessions/${this.sessionId}/stream`);
    this.eventSource?.close();
    this.eventSource = es;
    es.onmessage = (event: MessageEvent) => {
      const data: SseEvent = JSON.parse(event.data);
      this.sseEvents$.next(data);
    };
    es.onerror = () => {
      es.close();
    };
  }

  async sendMessage(message: string, platformContext?: { kubeconfig: string | null }): Promise<void> {
    if (!this.sessionId) throw new Error('No active session');
    const body: Record<string, unknown> = { message };
    if (platformContext) body['platform_context'] = platformContext;
    await firstValueFrom(
      this.http.post(`${API_URL}/sessions/${this.sessionId}/chat`, body)
    );
  }

  async approveTool(tool_use_id: string, approved: boolean): Promise<void> {
    if (!this.sessionId) throw new Error('No active session');
    await firstValueFrom(
      this.http.post(`${API_URL}/sessions/${this.sessionId}/approve`, {
        tool_use_id,
        approved,
      })
    );
  }

  closeStream(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }
}
