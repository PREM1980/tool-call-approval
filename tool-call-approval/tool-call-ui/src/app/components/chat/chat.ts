import {
  ChangeDetectorRef,
  Component,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  AfterViewChecked,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ChatService } from '../../services/chat.service';
import { WebsocketChatService } from '../../services/websocket-chat.service';
import { ToolApproval } from '../tool-approval/tool-approval';
import { Message, ToolCall } from '../../models/types';

export type ConnectionMode = 'sse' | 'websocket';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, ToolApproval],
  templateUrl: './chat.html',
  styleUrl: './chat.css',
})
export class Chat implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('messageList') private messageListRef!: ElementRef;

  messages: Message[] = [];
  userInput = '';
  pendingToolCall: ToolCall | null = null;
  isWaiting = false;
  mode: ConnectionMode = 'sse';
  isSwitching = false;

  private sseSubscription!: Subscription;
  private shouldScrollToBottom = false;

  constructor(
    private chatService: ChatService,
    private wsChatService: WebsocketChatService,
    private cdr: ChangeDetectorRef
  ) {}

  private get activeService(): ChatService | WebsocketChatService {
    return this.mode === 'sse' ? this.chatService : this.wsChatService;
  }

  async ngOnInit(): Promise<void> {
    await this.initConnection();
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  ngOnDestroy(): void {
    this.sseSubscription?.unsubscribe();
    this.activeService.closeStream();
  }

  async switchMode(newMode: ConnectionMode): Promise<void> {
    if (newMode === this.mode || this.isSwitching) return;
    this.isSwitching = true;
    this.sseSubscription?.unsubscribe();
    this.activeService.closeStream();
    this.messages = [];
    this.pendingToolCall = null;
    this.isWaiting = false;
    this.mode = newMode;
    await this.initConnection();
    this.isSwitching = false;
  }

  async sendMessage(): Promise<void> {
    const text = this.userInput.trim();
    if (!text) return;
    this.userInput = '';
    this.addMessage('user', text);
    this.isWaiting = true;
    await this.activeService.sendMessage(text);
  }

  async handleApproval(approved: boolean): Promise<void> {
    this.pendingToolCall = null;
    this.isWaiting = true;
    await this.activeService.approveTool(approved);
  }

  private async initConnection(): Promise<void> {
    await this.activeService.createSession();
    this.activeService.connectStream();
    this.sseSubscription = this.activeService.sseEvents$.subscribe((event) => {
      switch (event.type) {
        case 'thinking':
          this.isWaiting = true;
          break;
        case 'tool_call_pending':
          this.isWaiting = false;
          this.pendingToolCall = {
            tool_use_id: event.tool_use_id!,
            tool_name: event.tool_name!,
            tool_input: event.tool_input ?? {},
          };
          break;
        case 'tool_result':
          this.addSystemMessage(
            `Tool "${event.tool_name}" returned: ${event.result}`
          );
          break;
        case 'tool_rejected':
          this.addSystemMessage(`Tool "${event.tool_name}" was rejected.`);
          break;
        case 'message':
          this.isWaiting = false;
          this.addMessage('assistant', event.content ?? '');
          break;
        case 'done':
          this.isWaiting = false;
          // SSE closes on done and must reopen; WebSocket stays open
          if (this.mode === 'sse') {
            this.activeService.connectStream();
          }
          break;
        case 'error':
          this.isWaiting = false;
          this.addSystemMessage(`Error: ${event.content}`);
          break;
      }
      this.shouldScrollToBottom = true;
      this.cdr.detectChanges();
    });
  }

  private addMessage(role: 'user' | 'assistant', content: string): void {
    this.messages.push({
      id: crypto.randomUUID(),
      role,
      content,
      timestamp: new Date(),
    });
  }

  private addSystemMessage(content: string): void {
    this.messages.push({
      id: crypto.randomUUID(),
      role: 'system',
      content,
      timestamp: new Date(),
    });
  }

  private scrollToBottom(): void {
    try {
      const el = this.messageListRef?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    } catch {
      // ignore scroll errors in test env
    }
  }
}
