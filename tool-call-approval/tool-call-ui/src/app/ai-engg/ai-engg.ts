import { Component, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Chat } from '../components/chat/chat';
import { SessionSummary } from '../models/types';
import { SessionsService } from '../services/sessions.service';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-ai-engg',
  standalone: true,
  imports: [CommonModule, Chat, RouterLink, RouterLinkActive],
  templateUrl: './ai-engg.html',
  styleUrl: './ai-engg.css',
})
export class AiEngg implements OnInit {
  @ViewChild(Chat) private chat?: Chat;

  resumeSessionId: string | null = null;
  sessions: SessionSummary[] = [];
  loadingSessions = false;
  sessionsError = '';
  deletingSessionId: string | null = null;

  constructor(
    private sessionsService: SessionsService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    void this.refreshSessions();
  }

  async startNewChat(): Promise<void> {
    this.resumeSessionId = null;
    await this.chat?.newSession();
  }

  openSessionInChat(sessionId: string): void {
    this.resumeSessionId = sessionId;
  }

  async deleteSession(session: SessionSummary, event: MouseEvent): Promise<void> {
    event.stopPropagation();
    const title = this.sessionTitle(session);
    if (!window.confirm(`Delete the conversation “${title}”? This cannot be undone.`)) {
      return;
    }

    this.deletingSessionId = session.session_id;
    this.sessionsError = '';
    try {
      if (this.resumeSessionId === session.session_id) {
        await this.startNewChat();
      }
      await this.sessionsService.delete(session.session_id);
      this.sessions = this.sessions.filter(({ session_id }) => session_id !== session.session_id);
    } catch {
      this.sessionsError = 'Unable to delete this conversation.';
    } finally {
      this.deletingSessionId = null;
    }
  }

  async refreshSessions(): Promise<void> {
    this.loadingSessions = true;
    this.sessionsError = '';
    try {
      this.sessions = await this.sessionsService.getAll();
    } catch {
      this.sessionsError = 'Unable to load chat history.';
    } finally {
      this.loadingSessions = false;
    }
  }

  sessionTitle(session: SessionSummary): string {
    return session.first_message?.trim() || 'New conversation';
  }

  sessionTime(session: SessionSummary): string {
    const time = session.updated_at ?? session.created_at;
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
      .format(new Date(time * 1000));
  }
}
