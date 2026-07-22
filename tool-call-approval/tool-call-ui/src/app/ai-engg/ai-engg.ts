import { Component, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chat } from '../components/chat/chat';
import { SessionSummary } from '../models/types';
import { SessionsService } from '../services/sessions.service';

@Component({
  selector: 'app-ai-engg',
  standalone: true,
  imports: [CommonModule, Chat],
  templateUrl: './ai-engg.html',
  styleUrl: './ai-engg.css',
})
export class AiEngg implements OnInit {
  @ViewChild(Chat) private chat?: Chat;

  resumeSessionId: string | null = null;
  sessions: SessionSummary[] = [];
  loadingSessions = false;
  sessionsError = '';

  constructor(private sessionsService: SessionsService) {}

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
