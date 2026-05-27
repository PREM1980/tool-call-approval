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
import { AdminService, AgentInstance } from '../../services/admin.service';
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
  pendingToolCalls: ToolCall[] = [];
  isWaiting = false;
  mode: ConnectionMode = 'sse';
  isSwitching = false;
  instances: AgentInstance[] = [];
  selectedInstanceId: string | null = null;

  private sseSubscription!: Subscription;
  private shouldScrollToBottom = false;
  private kubeconfig: string | null = null;
  private pendingReportTitles = new Map<string, string>();

  constructor(
    private chatService: ChatService,
    private wsChatService: WebsocketChatService,
    private adminService: AdminService,
    private cdr: ChangeDetectorRef
  ) {}

  private get activeService(): ChatService | WebsocketChatService {
    return this.mode === 'sse' ? this.chatService : this.wsChatService;
  }

  async ngOnInit(): Promise<void> {
    const [creds, instances] = await Promise.all([
      this.adminService.getCredentials().catch(() => null),
      this.adminService.getAllAgentInstances().catch(() => []),
    ]);
    this.kubeconfig = creds?.kubeconfig ?? null;
    this.instances = instances;
    this.selectedInstanceId = instances[0]?.id ?? null;
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

  async newSession(): Promise<void> {
    if (this.isSwitching) return;
    this.isSwitching = true;
    this.sseSubscription?.unsubscribe();
    this.activeService.closeStream();
    this.messages = [];
    this.pendingToolCalls = [];
    this.isWaiting = false;
    await this.initConnection();
    this.isSwitching = false;
  }

  async onInstanceChange(): Promise<void> {
    await this.newSession();
  }

  async switchMode(newMode: ConnectionMode): Promise<void> {
    if (newMode === this.mode || this.isSwitching) return;
    this.isSwitching = true;
    this.sseSubscription?.unsubscribe();
    this.activeService.closeStream();
    this.messages = [];
    this.pendingToolCalls = [];
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
    const platformContext = this.kubeconfig ? { kubeconfig: this.kubeconfig } : undefined;
    await this.activeService.sendMessage(text, platformContext);
  }

  async handleApproval(tool_use_id: string, approved: boolean): Promise<void> {
    this.pendingToolCalls = this.pendingToolCalls.filter(tc => tc.tool_use_id !== tool_use_id);
    if (this.pendingToolCalls.length === 0) {
      this.isWaiting = true;
    }
    this.cdr.detectChanges();
    await this.activeService.approveTool(tool_use_id, approved);
  }

  private async initConnection(): Promise<void> {
    await this.activeService.createSession(this.selectedInstanceId ?? undefined);
    this.activeService.connectStream();
    this.sseSubscription = this.activeService.sseEvents$.subscribe((event) => {
      switch (event.type) {
        case 'thinking':
          this.isWaiting = true;
          break;
        case 'tool_call_pending':
          this.isWaiting = false;
          if (event.tool_name === 'save_report') {
            this.pendingReportTitles.set(
              event.tool_use_id!,
              String(event.tool_input?.['title'] ?? 'Report'),
            );
          }
          this.pendingToolCalls.push({
            tool_use_id: event.tool_use_id!,
            tool_name: event.tool_name!,
            tool_input: event.tool_input ?? {},
          });
          break;
        case 'tool_result':
          if (event.tool_name === 'save_report' && event.result) {
            const title = this.pendingReportTitles.get(event.tool_use_id!) ?? 'Report';
            this.pendingReportTitles.delete(event.tool_use_id!);
            this.addReportMessage(title, event.result);
          } else {
            this.addSystemMessage(
              `Tool "${event.tool_name}" returned: ${event.result}`
            );
          }
          break;
        case 'tool_rejected':
          this.pendingReportTitles.delete(event.tool_use_id!);
          this.addSystemMessage(`Tool "${event.tool_name}" was rejected.`);
          break;
        case 'message':
          this.isWaiting = false;
          this.appendAssistantMessage(event.content ?? '');
          break;
        case 'done':
          this.isWaiting = false;
          if (event.total_tokens) {
            this.addSystemMessage(
              `Tokens: ${event.total_tokens.toLocaleString()} total (${event.input_tokens?.toLocaleString()} in / ${event.output_tokens?.toLocaleString()} out)`
            );
          }
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

  private appendAssistantMessage(content: string): void {
    const last = this.messages.at(-1);
    if (last?.role === 'assistant') {
      last.content += content;
    } else {
      this.addMessage('assistant', content);
    }
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

  private addReportMessage(title: string, reportUrl: string): void {
    this.messages.push({
      id: crypto.randomUUID(),
      role: 'system',
      content: '',
      reportUrl,
      reportTitle: title,
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
