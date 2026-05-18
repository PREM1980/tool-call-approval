import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, firstValueFrom } from 'rxjs';
import { SseEvent } from '../models/types';

const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000';

@Injectable({ providedIn: 'root' })
export class WebsocketChatService {
  private sessionId: string | null = null;
  private ws: WebSocket | null = null;

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
    this.ws?.close();
    this.ws = new WebSocket(`${WS_URL}/sessions/${this.sessionId}/ws`);
    this.ws.onmessage = (event: MessageEvent) => {
      const data: SseEvent = JSON.parse(event.data);
      this.sseEvents$.next(data);
    };
    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  async sendMessage(message: string, platformContext?: { kubeconfig: string | null }): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('No active WebSocket connection');
    }
    this.ws.send(JSON.stringify({ type: 'chat', message, platform_context: platformContext ?? null }));
  }

  async approveTool(approved: boolean): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('No active WebSocket connection');
    }
    this.ws.send(JSON.stringify({ type: 'approve', approved }));
  }

  closeStream(): void {
    this.ws?.close();
    this.ws = null;
  }
}
