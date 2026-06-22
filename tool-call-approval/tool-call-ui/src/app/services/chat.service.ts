import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Subject, firstValueFrom } from 'rxjs';
import { ApiMessage, ApprovalContext, MessageEnvelope, SessionContext, SseEvent } from '../models/types';
import { createMessageEnvelope, emptySessionContext, normalizeSessionContext } from './envelope';
import { AuthService } from './auth.service';

const API_URL = '/api';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private sessionId: string | null = null;
  private sessionContext: SessionContext = emptySessionContext();
  private eventSource: EventSource | null = null;
  private authService = inject(AuthService);

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

  setSession(sessionId: string): void {
    this.sessionId = sessionId;
    this.sessionContext = normalizeSessionContext({ session_id: sessionId });
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
    const token = this.authService.accessToken();
    const suffix = token ? `?access_token=${encodeURIComponent(token)}` : '';
    const es = new EventSource(`${API_URL}/sessions/${this.sessionId}/stream${suffix}`);
    this.eventSource?.close();
    this.eventSource = es;
    es.onmessage = (event: MessageEvent) => {
      const data: SseEvent = JSON.parse(event.data);
      this.sseEvents$.next(data);
    };
    es.onerror = () => {
      es.close();
      if (this.eventSource === es) {
        this.sseEvents$.next({
          type: 'stream_error',
          content: 'Stream connection lost.',
        });
      }
    };
  }

  async sendMessage(messages: ApiMessage[]): Promise<void> {
    if (!this.sessionId) throw new Error('No active session');
    await firstValueFrom(
      this.http.post(
        `${API_URL}/sessions/${this.sessionId}/chat`,
        this.envelope({ ...this.sessionContext, session_id: this.sessionId }, messages),
      )
    );
  }

  async approveTool(tool_use_id: string, approved: boolean): Promise<void> {
    if (!this.sessionId) throw new Error('No active session');
    await firstValueFrom(
      this.http.post(
        `${API_URL}/sessions/${this.sessionId}/approve`,
        this.envelope(
          { ...this.sessionContext, session_id: this.sessionId },
          [],
          { tool_use_id, approved },
        ),
      )
    );
  }

  closeStream(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }

  private envelope(
    session: SessionContext,
    messages: ApiMessage[] = [],
    approval: ApprovalContext | null = null,
  ): MessageEnvelope {
    return createMessageEnvelope(session, messages, approval);
  }
}
