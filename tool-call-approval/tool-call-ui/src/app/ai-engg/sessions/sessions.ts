import { Component, OnInit, inject, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessage, SessionSummary } from '../../models/types';
import { SessionsService } from '../../services/sessions.service';
import { formatMarkdownBlocks, MarkdownBlock } from '../../shared/markdown-blocks';

export type SessionMessageBlock = MarkdownBlock;

export interface FormattedChatMessage extends ChatMessage {
  blocks: SessionMessageBlock[];
}

@Component({
  selector: 'app-sessions',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sessions.html',
  styleUrl: './sessions.css',
})
export class Sessions implements OnInit {
  private sessionsService = inject(SessionsService);

  @Output() openChat = new EventEmitter<string>();

  sessions: SessionSummary[] = [];
  selectedId: string | null = null;
  history: FormattedChatMessage[] = [];
  loadingSessions = false;
  loadingHistory = false;
  error = '';
  historyError = '';

  async ngOnInit(): Promise<void> {
    this.loadingSessions = true;
    try {
      this.sessions = await this.sessionsService.getAll();
    } catch {
      this.error = 'Failed to load sessions';
    } finally {
      this.loadingSessions = false;
    }
  }

  async selectSession(id: string): Promise<void> {
    if (this.selectedId === id) {
      this.selectedId = null;
      this.history = [];
      return;
    }
    this.selectedId = id;
    this.history = [];
    this.historyError = '';
    this.loadingHistory = true;
    try {
      const messages = await this.sessionsService.getHistory(id);
      this.history = messages.map(formatChatMessage);
    } catch {
      this.historyError = 'Failed to load chat history';
    } finally {
      this.loadingHistory = false;
    }
  }

  formatTimestamp(epoch: number): string {
    return new Date(epoch * 1000).toLocaleString();
  }

  shortId(id: string): string {
    return id.slice(0, 8);
  }
}

export function formatChatMessage(message: ChatMessage): FormattedChatMessage {
  return {
    ...message,
    blocks: formatMarkdownBlocks(message.content),
  };
}
