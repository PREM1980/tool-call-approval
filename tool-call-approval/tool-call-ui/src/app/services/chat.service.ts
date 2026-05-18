import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, firstValueFrom } from 'rxjs';
import { SseEvent } from '../models/types';

const API_URL = 'http://localhost:8000';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private sessionId: string | null = null;
  private eventSource: EventSource | null = null;

  readonly sseEvents$ = new Subject<SseEvent>();

  constructor(private http: HttpClient) {}

  async createSession(): Promise<void> {
    const res = await firstValueFrom(
      this.http.post<{ session_id: string }>(`${API_URL}/sessions`, {})
    );
    this.sessionId = res.session_id;
  }

  connectStream(): void {
    if (!this.sessionId) return;
    this.eventSource?.close();
    this.eventSource = new EventSource(
      `${API_URL}/sessions/${this.sessionId}/stream`
    );
    this.eventSource.onmessage = (event: MessageEvent) => {
      const data: SseEvent = JSON.parse(event.data);
      this.sseEvents$.next(data);
    };
    this.eventSource.onerror = () => {
      this.eventSource?.close();
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

  async approveTool(approved: boolean): Promise<void> {
    if (!this.sessionId) throw new Error('No active session');
    await firstValueFrom(
      this.http.post(`${API_URL}/sessions/${this.sessionId}/approve`, {
        approved,
      })
    );
  }

  closeStream(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }
}
