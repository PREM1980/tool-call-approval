import {
  ChangeDetectorRef,
  Component,
  Input,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  AfterViewChecked,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { Subscription } from 'rxjs';
import { marked } from 'marked';
import { AdminService, AgentInstance, SystemPromptData } from '../../services/admin.service';
import { ChatService } from '../../services/chat.service';
import { SessionsService } from '../../services/sessions.service';
import { WebsocketChatService } from '../../services/websocket-chat.service';
import { ToolApproval } from '../tool-approval/tool-approval';
import { Message, ToolCall } from '../../models/types';

export type ConnectionMode = 'sse' | 'websocket';

const KUBERNETES_SUGGESTIONS = [
  'List all pods in the default namespace',
  'Scale the frontend deployment to 3 replicas',
  'Show me recent events in the kube-system namespace',
];

const GENERIC_SUGGESTIONS = [
  'Summarize this text in three bullet points',
  'Draft a concise status update',
  'Help me debug this error message',
];

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule, ToolApproval],
  templateUrl: './chat.html',
  styleUrl: './chat.css',
})
export class Chat implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('messageList') private messageListRef!: ElementRef;
  @Input() resumeSessionId?: string | null;

  messages: Message[] = [];
  userInput = '';
  pendingToolCalls: ToolCall[] = [];
  isWaiting = false;
  mode: ConnectionMode = 'sse';
  isSwitching = false;
  instances: AgentInstance[] = [];
  selectedInstanceId: string | null = null;
  systemPrompts: SystemPromptData[] = [];
  selectedSystemPromptId: string | null = null;

  private sseSubscription!: Subscription;
  private shouldScrollToBottom = false;
  private kubeconfig: string | null = null;
  private pendingReportTitles = new Map<string, string>();

  constructor(
    private chatService: ChatService,
    private wsChatService: WebsocketChatService,
    private sessionsService: SessionsService,
    private adminService: AdminService,
    private cdr: ChangeDetectorRef,
    private sanitizer: DomSanitizer,
  ) {}

  renderMarkdown(content: string): SafeHtml {
    return this.sanitizer.bypassSecurityTrustHtml(marked.parse(this.fixMdTables(content)) as string);
  }

  private fixMdTables(content: string): string {
    // LLMs often emit "# Title | col1 | col2 |" — split into heading + table header row
    return content.replace(
      /^(#{1,6})\s*([^|\n]+?)\s*\|\s*(.+)$/gm,
      (_, hashes, title, rest) => `${hashes} ${title.trim()}\n| ${rest}`,
    );
  }

  private get activeService(): ChatService | WebsocketChatService {
    return this.mode === 'sse' ? this.chatService : this.wsChatService;
  }

  get emptyStateSuggestions(): string[] {
    const promptName = this.selectedSystemPromptName.toLowerCase();
    return promptName.includes('kubernetes')
      ? KUBERNETES_SUGGESTIONS
      : GENERIC_SUGGESTIONS;
  }

  private get selectedSystemPromptName(): string {
    return this.systemPrompts.find(prompt => prompt.id === this.selectedSystemPromptId)?.name ?? '';
  }

  async ngOnInit(): Promise<void> {
    const [creds, instances, systemPrompts] = await Promise.all([
      this.adminService.getCredentials().catch(() => null),
      this.adminService.getAllAgentInstances().catch(() => []),
      this.adminService.listSystemPrompts().catch(() => []),
    ]);
    this.kubeconfig = creds?.kubeconfig ?? null;
    this.instances = instances;
    this.selectedInstanceId = instances[0]?.id ?? null;
    this.systemPrompts = systemPrompts;
    this.selectedSystemPromptId = this.getInitialSystemPromptId(systemPrompts);
    if (this.resumeSessionId) {
      await this.loadExistingSession(this.resumeSessionId);
    } else {
      await this.initConnection();
    }
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

  async onSystemPromptSelect(promptId: string): Promise<void> {
    if (this.isSwitching || this.isWaiting || promptId === this.selectedSystemPromptId) return;
    this.selectedSystemPromptId = promptId;
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
    try {
      await this.activeService.sendMessage(text, platformContext);
    } catch (error) {
      this.isWaiting = false;
      this.addSystemMessage(`Error: ${this.describeRequestError(error)}`);
      this.shouldScrollToBottom = true;
      this.cdr.detectChanges();
    }
  }

  async handleApproval(tool_use_id: string, approved: boolean): Promise<void> {
    this.pendingToolCalls = this.pendingToolCalls.filter(tc => tc.tool_use_id !== tool_use_id);
    if (this.pendingToolCalls.length === 0) {
      this.isWaiting = true;
    }
    this.cdr.detectChanges();
    await this.activeService.approveTool(tool_use_id, approved);
  }

  private async loadExistingSession(sessionId: string): Promise<void> {
    this.mode = 'sse';
    this.chatService.setSession(sessionId);
    const history = await this.sessionsService.getHistory(sessionId).catch(() => []);
    this.messages = history.map(m => ({
      id: crypto.randomUUID(),
      role: m.role,
      content: m.content,
      timestamp: new Date(),
    }));
    this.shouldScrollToBottom = true;
    this.subscribeToEvents(this.chatService);
  }

  private async initConnection(): Promise<void> {
    await this.activeService.createSession(
      this.selectedInstanceId ?? undefined,
      this.selectedSystemPromptId ?? undefined,
    );
    this.subscribeToEvents(this.activeService);
  }

  private getInitialSystemPromptId(prompts: SystemPromptData[]): string | null {
    if (
      this.selectedSystemPromptId &&
      prompts.some(prompt => prompt.id === this.selectedSystemPromptId)
    ) {
      return this.selectedSystemPromptId;
    }
    return prompts.find(prompt => prompt.is_active)?.id ?? prompts[0]?.id ?? null;
  }

  private subscribeToEvents(service: ChatService | WebsocketChatService): void {
    service.connectStream();
    this.sseSubscription = service.sseEvents$.subscribe((event) => {
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
        case 'stream_error':
          if (this.isWaiting || this.pendingToolCalls.length > 0) {
            this.isWaiting = false;
            this.addSystemMessage(`Error: ${event.content ?? 'Stream connection lost.'}`);
          }
          break;
      }
      this.shouldScrollToBottom = true;
      this.cdr.detectChanges();
    });
  }

  private describeRequestError(error: unknown): string {
    if (error && typeof error === 'object') {
      const maybeHttpError = error as {
        error?: { detail?: string; message?: string };
        message?: string;
        status?: number;
      };
      const detail = maybeHttpError.error?.detail ?? maybeHttpError.error?.message ?? maybeHttpError.message;
      if (detail) return detail;
      if (maybeHttpError.status === 404) return 'Session not found. Start a new chat and try again.';
    }
    return 'Could not send message. Please try again.';
  }

  private appendAssistantMessage(content: string): void {
    if (!content.trim()) return;
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
