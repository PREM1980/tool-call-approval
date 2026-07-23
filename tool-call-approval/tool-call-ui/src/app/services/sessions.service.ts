import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { ChatMessage, DebugEvent, SessionSummary } from '../models/types';

const API_URL = '/api';

@Injectable({ providedIn: 'root' })
export class SessionsService {
  private http = inject(HttpClient);

  getAll(): Promise<SessionSummary[]> {
    return firstValueFrom(
      this.http.get<SessionSummary[]>(`${API_URL}/sessions`)
    );
  }

  getHistory(sessionId: string): Promise<ChatMessage[]> {
    return firstValueFrom(
      this.http.get<ChatMessage[]>(`${API_URL}/sessions/${sessionId}/history`)
    );
  }

  getEvents(sessionId: string, afterSequence = 0): Promise<DebugEvent[]> {
    return firstValueFrom(
      this.http.get<DebugEvent[]>(`${API_URL}/sessions/${sessionId}/events`, {
        params: { after_sequence: afterSequence },
      })
    );
  }

  delete(sessionId: string): Promise<{ status: string }> {
    return firstValueFrom(
      this.http.delete<{ status: string }>(`${API_URL}/sessions/${sessionId}`)
    );
  }
}
