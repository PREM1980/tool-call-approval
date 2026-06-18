import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, firstValueFrom } from 'rxjs';
import { ApiMessage, ApprovalContext, MessageEnvelope, SessionContext, SseEvent } from '../models/types';
import { createMessageEnvelope, emptySessionContext, normalizeSessionContext } from './envelope';

const API_URL = 'http://localhost:8000';
const WS_URL = 'ws://localhost:8000';

@Injectable({ providedIn: 'root' })
export class WebsocketChatService {
  private sessionId: string | null = null;
  private sessionContext: SessionContext = emptySessionContext();
  private ws: WebSocket | null = null;

  readonly sseEvents$ = new Subject<SseEvent>();

  constructor(private http: HttpClient) {}

  async createSession(
    instanceId?: string | null,
    personaId?: string | null,
    systemPromptId?: string | null,
    modelId?: string | null,
    provider?: string | null,
    personaIds: string[] = [],
  ): Promise<void> {
    const session: SessionContext = normalizeSessionContext({
      session_id: null,
      instance_id: instanceId ?? null,
      persona_id: personaId ?? null,
      persona_ids: personaIds,
      system_prompt_id: systemPromptId ?? null,
      model_id: modelId ?? null,
      provider: provider ?? null,
    });
    const res = await firstValueFrom(
      this.http.post<{ session_id: string }>(
        `${API_URL}/sessions`,
        this.envelope(session),
      )
    );
    this.sessionId = res.session_id;
    this.sessionContext = normalizeSessionContext({
      ...session,
      session_id: res.session_id,
    });
  }

  updateSessionContext(context: Partial<SessionContext>): void {
    this.sessionContext = normalizeSessionContext({
      ...this.sessionContext,
      ...context,
      session_id: this.sessionId,
    });
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
      this.sseEvents$.next({
        type: 'stream_error',
        content: 'WebSocket connection lost.',
      });
      this.ws?.close();
    };
  }

  async sendMessage(messages: ApiMessage[]): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('No active WebSocket connection');
    }
    this.ws.send(JSON.stringify({
      type: 'chat',
      ...this.envelope({ ...this.sessionContext, session_id: this.sessionId }, messages),
    }));
  }

  async approveTool(tool_use_id: string, approved: boolean): Promise<void> {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('No active WebSocket connection');
    }
    this.ws.send(JSON.stringify({
      type: 'approve',
      ...this.envelope(
        { ...this.sessionContext, session_id: this.sessionId },
        [],
        { tool_use_id, approved },
      ),
    }));
  }

  closeStream(): void {
    this.ws?.close();
    this.ws = null;
  }

  private envelope(
    session: SessionContext,
    messages: ApiMessage[] = [],
    approval: ApprovalContext | null = null,
  ): MessageEnvelope {
    return createMessageEnvelope(session, messages, approval);
  }
}
