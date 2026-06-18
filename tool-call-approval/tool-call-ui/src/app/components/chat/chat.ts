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
import { Subscription } from 'rxjs';
import { AdminService, PersonaData, Skill, SystemPromptData } from '../../services/admin.service';
import { ChatService } from '../../services/chat.service';
import { SessionsService } from '../../services/sessions.service';
import { WebsocketChatService } from '../../services/websocket-chat.service';
import { ToolApproval } from '../tool-approval/tool-approval';
import { AmbientContext, ApiMessage, Command, ExecutedCommand, Message, MessageData, PlatformContext, SseEvent, ToolCall } from '../../models/types';
import { formatMarkdownBlocks, MarkdownBlock } from '../../shared/markdown-blocks';

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
  personas: PersonaData[] = [];
  skills: Skill[] = [];
  selectedPersonaIds: string[] = [];
  systemPrompts: SystemPromptData[] = [];
  selectedSystemPromptId: string | null = null;
  selectedProvider: string = 'LOCAL';
  selectedModelId: string = 'nemotron-3-super';

  readonly availableProviders = ['AWS', 'GCP', 'LOCAL'];
  readonly availableModels = [
    'devstral',
    'gemma-4',
    'gpt-oss-120b',
    'nemotron-3-nano',
    'nemotron-3-super',
    'nemotron-3-ultra',
  ];

  private sseSubscription!: Subscription;
  private shouldScrollToBottom = false;
  private kubeconfig: string | null = null;
  private pendingReportTitles = new Map<string, string>();
  private activeToolData: MessageData = this.emptyMessageData();
  private activeToolCommands = new Map<string, Command>();

  constructor(
    private chatService: ChatService,
    private wsChatService: WebsocketChatService,
    private sessionsService: SessionsService,
    private adminService: AdminService,
    private cdr: ChangeDetectorRef,
  ) {}

  formatMessageContent(content: string): MarkdownBlock[] {
    return formatMarkdownBlocks(content);
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
    const [creds, personas, skills, systemPrompts] = await Promise.all([
      this.adminService.getCredentials().catch(() => null),
      this.adminService.getPersonas().catch(() => []),
      this.adminService.getSkills().catch(() => []),
      this.adminService.listSystemPrompts().catch(() => []),
    ]);
    this.kubeconfig = creds?.kubeconfig ?? null;
    this.personas = personas;
    this.skills = skills;
    this.selectedPersonaIds = personas[0]?.id ? [personas[0].id] : [];
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
    this.resetActiveToolData();
    await this.initConnection();
    this.isSwitching = false;
  }

  async onProviderChange(): Promise<void> {
    await this.newSession();
  }

  async onModelChange(): Promise<void> {
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
    this.resetActiveToolData();
    this.mode = newMode;
    await this.initConnection();
    this.isSwitching = false;
  }

  async sendMessage(): Promise<void> {
    const text = this.userInput.trim();
    if (!text) return;
    this.userInput = '';
    const userMessage = this.addMessage('user', text);
    this.isWaiting = true;
    const platformContext = this.kubeconfig ? { kubeconfig: this.kubeconfig } : undefined;
    try {
      await this.activeService.sendMessage(
        this.buildRequestMessages(userMessage.id, platformContext),
      );
    } catch (error) {
      this.isWaiting = false;
      this.addSystemMessage(`Error: ${this.describeRequestError(error)}`);
      this.shouldScrollToBottom = true;
      this.cdr.detectChanges();
    }
  }

  async handleApproval(tool_use_id: string, approved: boolean): Promise<void> {
    this.pendingToolCalls = this.pendingToolCalls.filter(tc => tc.tool_use_id !== tool_use_id);
    this.markToolApproval(tool_use_id, approved);
    if (this.pendingToolCalls.length === 0) {
      this.isWaiting = true;
    }
    this.attachActiveToolDataToLatestAssistant();
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
      timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
      data: this.cloneMessageData(m.data ?? this.emptyMessageData()),
      user: m.user ?? null,
      agent: m.agent ?? null,
      platform_context: m.role === 'user'
        ? this.normalizePlatformContext(m.platform_context)
        : undefined,
      ambient_context: m.role === 'user'
        ? this.normalizeAmbientContext(m.ambient_context)
        : undefined,
    }));
    this.shouldScrollToBottom = true;
    this.subscribeToEvents(this.chatService);
  }

  private async initConnection(): Promise<void> {
    const personaIds = [...this.selectedPersonaIds];
    await this.activeService.createSession(
      null,
      personaIds[0] ?? undefined,
      this.selectedSystemPromptId ?? undefined,
      this.selectedProvider === 'LOCAL' ? this.selectedModelId || undefined : undefined,
      this.selectedProvider,
      personaIds,
    );
    this.subscribeToEvents(this.activeService);
  }

  selectedPersonaSkillSummary(): string {
    const skillIds = this.selectedPersonaIds
      .flatMap(personaId => this.personas.find(p => p.id === personaId)?.skill_ids ?? []);
    const uniqueSkillIds = [...new Set(skillIds)];
    if (uniqueSkillIds.length === 0) return 'No skills';
    return uniqueSkillIds
      .map(id => this.skills.find(skill => skill.id === id)?.filename ?? id)
      .join(', ');
  }

  isPersonaSelected(personaId: string): boolean {
    return this.selectedPersonaIds.includes(personaId);
  }

  async togglePersonaSelection(personaId: string, selected: boolean): Promise<void> {
    if (this.isSwitching || this.isWaiting) return;
    const current = new Set(this.selectedPersonaIds);
    if (selected) {
      current.add(personaId);
    } else {
      current.delete(personaId);
    }
    const next = this.personas
      .map(persona => persona.id)
      .filter(id => current.has(id));
    if (next.join('|') === this.selectedPersonaIds.join('|')) return;
    this.selectedPersonaIds = next;
    this.activeService.updateSessionContext({
      persona_id: next[0] ?? null,
      persona_ids: next,
    });
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
          this.trackToolCommand(event);
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
          this.trackToolResult(event);
          if (event.tool_name === 'save_report' && event.result) {
            const title = this.pendingReportTitles.get(event.tool_use_id!) ?? 'Report';
            this.pendingReportTitles.delete(event.tool_use_id!);
            this.addReportMessage(title, event.result);
          } else if (this.shouldShowToolResult(event)) {
            this.addSystemMessage(
              `Tool "${event.tool_name}" returned: ${event.result}`
            );
          }
          break;
        case 'tool_rejected':
          this.markToolApproval(event.tool_use_id, false);
          this.attachActiveToolDataToLatestAssistant();
          this.pendingReportTitles.delete(event.tool_use_id!);
          this.addSystemMessage(`Tool "${event.tool_name}" was rejected.`);
          break;
        case 'message':
          this.isWaiting = false;
          this.attachActiveToolDataToMessage(
            this.appendAssistantMessage(event.content ?? ''),
          );
          break;
        case 'done':
          this.isWaiting = false;
          this.attachActiveToolDataToLatestAssistant();
          this.resetActiveToolData();
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

  private appendAssistantMessage(content: string): Message | null {
    if (!content.trim()) return null;
    const last = this.messages.at(-1);
    if (last?.role === 'assistant') {
      last.content += content;
      return last;
    } else {
      return this.addMessage('assistant', content);
    }
  }

  private trackToolCommand(event: SseEvent): void {
    if (!event.tool_use_id || !event.tool_name) return;
    const commandText = this.formatToolCommand(event.tool_name, event.tool_input);
    if (!commandText) return;
    const command: Command = { command: commandText, execute: false };
    this.activeToolCommands.set(event.tool_use_id, command);
    this.activeToolData.cmds.push(command);
    this.attachActiveToolDataToLatestAssistant();
  }

  private trackToolResult(event: SseEvent): void {
    if (!event.tool_use_id) return;
    const command = this.activeToolCommands.get(event.tool_use_id);
    if (!command) return;
    command.execute = true;
    delete command.rejection_reason;
    const executed: ExecutedCommand = {
      command: command.command,
      output: event.result ?? '',
    };
    this.activeToolData.executed_cmds.push(executed);
    this.attachActiveToolDataToLatestAssistant();
  }

  private markToolApproval(toolUseId: string | undefined, approved: boolean): void {
    if (!toolUseId) return;
    const command = this.activeToolCommands.get(toolUseId);
    if (!command) return;
    command.execute = approved;
    if (approved) {
      delete command.rejection_reason;
    } else {
      command.rejection_reason = 'User rejected tool call';
    }
  }

  private formatToolCommand(
    toolName: string,
    toolInput: Record<string, unknown> | undefined,
  ): string | null {
    if (toolName === 'kubectl') {
      const args = String(toolInput?.['args'] ?? '').trim();
      return args ? `kubectl ${args}` : 'kubectl';
    }
    if (Object.keys(toolInput ?? {}).length === 0) {
      return toolName;
    }
    return `${toolName}(${JSON.stringify(toolInput)})`;
  }

  private shouldShowToolResult(event: SseEvent): boolean {
    return event.tool_name !== 'get_skill_instructions';
  }

  private attachActiveToolDataToLatestAssistant(): void {
    const lastAssistant = [...this.messages].reverse().find(message => message.role === 'assistant');
    this.attachActiveToolDataToMessage(lastAssistant ?? null);
  }

  private attachActiveToolDataToMessage(message: Message | null): void {
    if (!message || message.role !== 'assistant' || !this.hasToolData(this.activeToolData)) return;
    message.data = this.cloneMessageData(this.activeToolData);
  }

  private resetActiveToolData(): void {
    this.activeToolData = this.emptyMessageData();
    this.activeToolCommands.clear();
  }

  private emptyMessageData(): MessageData {
    return {
      cmds: [],
      executed_cmds: [],
      url_configs: [],
      user_file_uploads: [],
    };
  }

  private emptyPlatformContext(): PlatformContext {
    return {
      k8s_namespace: null,
      duplo_base_url: null,
      duplo_token: null,
      tenant_name: null,
      aws_credentials: null,
      kubeconfig: null,
    };
  }

  private emptyAmbientContext(): AmbientContext {
    return { user_terminal_cmds: [] };
  }

  private hasToolData(data: MessageData): boolean {
    return data.cmds.length > 0 || data.executed_cmds.length > 0;
  }

  private cloneMessageData(data: MessageData): MessageData {
    return {
      cmds: data.cmds.map(command => ({ ...command })),
      executed_cmds: data.executed_cmds.map(command => ({ ...command })),
      url_configs: data.url_configs.map(config => ({ ...config })),
      user_file_uploads: data.user_file_uploads.map(file => ({ ...file })),
    };
  }

  private normalizePlatformContext(context?: PlatformContext | null): PlatformContext {
    return {
      ...this.emptyPlatformContext(),
      ...(context ?? {}),
    };
  }

  private normalizeAmbientContext(context?: AmbientContext | null): AmbientContext {
    return {
      user_terminal_cmds: (context?.user_terminal_cmds ?? []).map(command => ({ ...command })),
    };
  }

  private buildRequestMessages(
    latestUserMessageId: string,
    platformContext?: PlatformContext,
  ): ApiMessage[] {
    return this.messages
      .filter((message): message is Message & { role: 'user' | 'assistant' } =>
        message.role === 'user' || message.role === 'assistant'
      )
      .map((message) => {
        const apiMessage: ApiMessage = {
          role: message.role,
          content: message.content,
          data: this.cloneMessageData(message.data ?? this.emptyMessageData()),
          timestamp: message.timestamp.toISOString(),
          user: message.user ?? null,
          agent: message.agent ?? null,
        };
        if (message.role === 'user') {
          apiMessage.platform_context = this.normalizePlatformContext(message.platform_context);
          apiMessage.ambient_context = this.normalizeAmbientContext(message.ambient_context);
          if (message.id === latestUserMessageId) {
            apiMessage.platform_context = this.normalizePlatformContext({
              ...apiMessage.platform_context,
              ...(platformContext ?? {}),
            });
          }
        }
        return apiMessage;
      });
  }

  private addMessage(role: 'user' | 'assistant', content: string): Message {
    const message: Message = {
      id: crypto.randomUUID(),
      role,
      content,
      timestamp: new Date(),
      data: this.emptyMessageData(),
      user: null,
      agent: null,
    };
    if (role === 'user') {
      message.platform_context = this.emptyPlatformContext();
      message.ambient_context = this.emptyAmbientContext();
    }
    this.messages.push(message);
    return message;
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
