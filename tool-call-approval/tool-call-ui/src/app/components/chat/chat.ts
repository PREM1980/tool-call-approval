import {
  ChangeDetectorRef,
  Component,
  EventEmitter,
  Input,
  OnChanges,
  OnInit,
  OnDestroy,
  Output,
  SimpleChanges,
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
import { ToolApproval } from '../tool-approval/tool-approval';
import { AmbientContext, ApiMessage, ApprovalDecision, Command, DebugEvent, ExecutedCommand, Message, MessageData, PlatformContext, SseEvent, ToolCall } from '../../models/types';
import { formatMarkdownBlocks, MarkdownBlock } from '../../shared/markdown-blocks';

const KUBERNETES_SUGGESTIONS = [
  'List all pods',
  'List all namespaces',
  'list all applications in argo cd',
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
export class Chat implements OnInit, OnChanges, OnDestroy, AfterViewChecked {
  @ViewChild('messageList') private messageListRef!: ElementRef;
  @Input() resumeSessionId?: string | null;
  @Output() sessionChanged = new EventEmitter<void>();

  messages: Message[] = [];
  userInput = '';
  pendingToolCalls: ToolCall[] = [];
  executionEvents: DebugEvent[] = [];
  isWaiting = false;
  activityStatus = '';
  showScrollToLatest = false;
  isSwitching = false;
  personas: PersonaData[] = [];
  skills: Skill[] = [];
  selectedPersonaIds: string[] = [];
  systemPrompts: SystemPromptData[] = [];
  selectedSystemPromptId: string | null = null;
  selectedPromptTemplate = '';
  selectedModelId: string = 'gemma-4';

  readonly availableModels = [
    'gpt-oss-120b',
    'devstral',
    'gemma-4',
    'nemotron-3-nano',
    'nemotron-3-super',
    'nemotron-3-ultra',
    'nemotron-3-ultra-codex',
  ];

  private sseSubscription!: Subscription;
  private shouldScrollToBottom = false;
  private kubeconfig: string | null = null;
  private hasActiveSession = false;
  private pendingReportTitles = new Map<string, string>();
  private activeToolData: MessageData = this.emptyMessageData();
  private activeToolCommands = new Map<string, Command>();
  private streamingAssistantMessage: Message | null = null;
  private followLatest = true;

  constructor(
    private chatService: ChatService,
    private sessionsService: SessionsService,
    private adminService: AdminService,
    private cdr: ChangeDetectorRef,
  ) {}

  formatMessageContent(content: string): MarkdownBlock[] {
    return formatMarkdownBlocks(content);
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

  get canSendMessage(): boolean {
    return this.hasActiveSession;
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
      this.hasActiveSession = false;
      await this.initConnection();
    }
  }

  async ngOnChanges(changes: SimpleChanges): Promise<void> {
    const sessionChange = changes['resumeSessionId'];
    if (!sessionChange || sessionChange.firstChange || !this.resumeSessionId || !this.hasActiveSession) return;
    await this.openExistingSession(this.resumeSessionId);
  }

  ngAfterViewChecked(): void {
    if (this.shouldScrollToBottom && this.followLatest) {
      this.scrollToBottom();
    }
    this.shouldScrollToBottom = false;
    this.updateScrollToLatestButton();
  }

  onMessageScroll(): void {
    const messageList = this.messageListRef?.nativeElement;
    if (!messageList) return;
    this.followLatest = this.isNearMessageListBottom(messageList);
    this.updateScrollToLatestButton();
  }

  scrollToLatest(): void {
    const messageList = this.messageListRef?.nativeElement;
    if (!messageList) return;
    this.followLatest = true;
    messageList.scrollTo({ top: messageList.scrollHeight, behavior: 'smooth' });
    this.showScrollToLatest = false;
  }

  ngOnDestroy(): void {
    this.sseSubscription?.unsubscribe();
    this.chatService.closeStream();
  }

  async newSession(): Promise<void> {
    if (this.isSwitching) return;
    this.isSwitching = true;
    try {
      this.sseSubscription?.unsubscribe();
      this.chatService.closeStream();
      this.messages = [];
      this.pendingToolCalls = [];
      this.executionEvents = [];
      this.isWaiting = false;
      this.activityStatus = '';
      this.followLatest = true;
      this.showScrollToLatest = false;
      this.hasActiveSession = false;
      this.resetActiveToolData();
      this.streamingAssistantMessage = null;
      await this.initConnection();
    } finally {
      this.isSwitching = false;
    }
  }

  private async openExistingSession(sessionId: string): Promise<void> {
    if (this.isSwitching) return;
    this.isSwitching = true;
    try {
      this.sseSubscription?.unsubscribe();
      this.chatService.closeStream();
      this.messages = [];
      this.pendingToolCalls = [];
      this.executionEvents = [];
      this.isWaiting = false;
      this.activityStatus = '';
      this.followLatest = true;
      this.showScrollToLatest = false;
      this.hasActiveSession = false;
      this.resetActiveToolData();
      this.streamingAssistantMessage = null;
      await this.loadExistingSession(sessionId);
    } finally {
      this.isSwitching = false;
    }
  }

  async onModelChange(): Promise<void> {
    await this.newSession();
  }

  async onPersonaChange(personaId: string): Promise<void> {
    if (this.isSwitching || this.isWaiting) return;
    this.selectedPersonaIds = personaId ? [personaId] : [];
    if (this.hasActiveSession) {
      this.chatService.updateSessionContext({
        persona_id: personaId || null,
        persona_ids: this.selectedPersonaIds,
      });
    }
  }

  onQueryKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Enter' || event.shiftKey) return;
    event.preventDefault();
    void this.sendMessage();
  }

  selectPromptTemplate(template: string): void {
    if (!template) return;
    this.userInput = template;
    this.selectedPromptTemplate = '';
  }

  async onSystemPromptSelect(promptId: string): Promise<void> {
    if (this.isSwitching || this.isWaiting) return;
    this.selectedSystemPromptId = promptId === this.selectedSystemPromptId ? null : promptId;
    await this.newSession();
  }

  async sendMessage(): Promise<void> {
    const text = this.userInput.trim();
    if (!text || !this.canSendMessage) return;
    this.userInput = '';
    const userMessage = this.addMessage('user', text);
    this.isWaiting = true;
    this.activityStatus = 'Thinking…';
    const platformContext = this.kubeconfig ? { kubeconfig: this.kubeconfig } : undefined;
    try {
      await this.chatService.sendMessage(
        this.buildRequestMessages(userMessage.id, platformContext),
      );
    } catch (error) {
      this.isWaiting = false;
      this.activityStatus = '';
      this.addSystemMessage(`Error: ${this.describeRequestError(error)}`);
      this.shouldScrollToBottom = true;
      this.cdr.detectChanges();
    }
  }

  async handleApproval(tool_use_id: string, decision: ApprovalDecision): Promise<void> {
    const { approved, tool_input } = decision;
    this.pendingToolCalls = this.pendingToolCalls.filter(tc => tc.tool_use_id !== tool_use_id);
    this.markToolApproval(tool_use_id, approved);
    if (this.pendingToolCalls.length === 0) {
      this.isWaiting = true;
      this.activityStatus = 'Working…';
    }
    this.attachActiveToolDataToLatestAssistant();
    this.cdr.detectChanges();
    await this.chatService.approveTool(tool_use_id, approved, tool_input);
  }

  private async loadExistingSession(sessionId: string): Promise<void> {
    this.chatService.setSession(sessionId);
    this.hasActiveSession = true;
    const [history, events] = await Promise.all([
      this.sessionsService.getHistory(sessionId).catch(() => []),
      this.sessionsService.getEvents(sessionId).catch(() => []),
    ]);
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
    this.executionEvents = events;
    this.shouldScrollToBottom = true;
    this.subscribeToEvents(this.chatService);
  }

  private async initConnection(): Promise<void> {
    if (this.systemPrompts.length > 0 && !this.selectedSystemPromptId) return;
    const personaIds = [...this.selectedPersonaIds];
    await this.chatService.createSession(
      null,
      personaIds[0] ?? undefined,
      this.selectedSystemPromptId ?? undefined,
      this.selectedModelId || undefined,
      'LOCAL',
      personaIds,
    );
    this.hasActiveSession = true;
    this.subscribeToEvents(this.chatService);
    this.sessionChanged.emit();
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
    this.chatService.updateSessionContext({
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

  private subscribeToEvents(service: ChatService): void {
    service.connectStream();
    this.sseSubscription = service.sseEvents$.subscribe((event) => {
      if (event.type !== 'stream_error') this.addLiveExecutionEvent(event);
      switch (event.type) {
        case 'thinking':
          this.isWaiting = true;
          this.activityStatus = 'Thinking…';
          break;
        case 'model_request':
          this.isWaiting = true;
          this.activityStatus = 'Thinking…';
          break;
        case 'tool_call_pending':
          this.isWaiting = false;
          this.activityStatus = '';
          // A following model pass starts a separate assistant message after the tool result.
          this.streamingAssistantMessage = null;
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
        case 'message_delta':
          this.isWaiting = false;
          this.activityStatus = '';
          this.appendAssistantDelta(event.content ?? '', event.run_id);
          break;
        case 'tool_started':
          this.isWaiting = true;
          this.activityStatus = event.tool_name ? `Working: ${event.tool_name}…` : 'Working…';
          break;
        case 'tool_result':
          this.isWaiting = true;
          this.activityStatus = 'Thinking…';
          this.trackToolResult(event);
          if (event.tool_name === 'save_report' && event.result) {
            const title = this.pendingReportTitles.get(event.tool_use_id!) ?? 'Report';
            this.pendingReportTitles.delete(event.tool_use_id!);
            this.addReportMessage(title, event.result);
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
          this.activityStatus = '';
          const streamed = this.streamingAssistantMessage;
          const assistantMessage = streamed?.content === (event.content ?? '')
            ? streamed
            : this.appendAssistantMessage(event.content ?? '');
          this.attachActiveToolDataToMessage(assistantMessage);
          if (assistantMessage) assistantMessage.trace_run_id = event.run_id ?? assistantMessage.trace_run_id;
          this.streamingAssistantMessage = null;
          break;
        case 'done':
          this.isWaiting = false;
          this.activityStatus = '';
          this.attachActiveToolDataToLatestAssistant();
          this.resetActiveToolData();
          if (event.total_tokens) {
            this.addSystemMessage(
              `Tokens: ${event.total_tokens.toLocaleString()} total (${event.input_tokens?.toLocaleString()} in / ${event.output_tokens?.toLocaleString()} out)`
            );
          }
          this.chatService.connectStream();
          break;
        case 'error':
          this.isWaiting = false;
          this.activityStatus = '';
          this.addSystemMessage(`Error: ${event.content}`);
          break;
        case 'stream_error':
          if (this.isWaiting || this.pendingToolCalls.length > 0) {
            this.isWaiting = false;
            this.activityStatus = '';
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
        error?: { detail?: string | Array<{ msg?: string }>; message?: string };
        message?: string;
        status?: number;
      };
      const detail = maybeHttpError.error?.detail ?? maybeHttpError.error?.message ?? maybeHttpError.message;
      if (Array.isArray(detail)) {
        return detail.map(item => item.msg ?? 'Invalid request').join('; ');
      }
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

  traceEventsFor(message: Message): DebugEvent[] {
    const runId = message.trace_run_id
      ?? (typeof message.agent === 'object' && message.agent ? message.agent['run_id'] : null);
    return runId ? this.executionEvents.filter(event => event.run_id === runId) : [];
  }

  private appendAssistantDelta(content: string, runId?: string | null): void {
    if (!content) return;
    if (!this.streamingAssistantMessage) {
      this.streamingAssistantMessage = this.addMessage('assistant', '');
    }
    this.streamingAssistantMessage.content += content;
    this.streamingAssistantMessage.trace_run_id = runId ?? this.streamingAssistantMessage.trace_run_id;
  }

  eventSummary(event: DebugEvent): string {
    const payload = event.payload;
    const tool = typeof payload['tool_name'] === 'string' ? `: ${payload['tool_name']}` : '';
    const content = typeof payload['content'] === 'string' ? ` — ${payload['content']}` : '';
    const result = typeof payload['result'] === 'string' ? ` — ${payload['result']}` : '';
    return `${event.event_type.replaceAll('_', ' ')}${tool}${content || result}`;
  }

  private addLiveExecutionEvent(event: SseEvent): void {
    if (event.sequence && this.executionEvents.some(item => item.sequence === event.sequence)) return;
    const { type, sequence, run_id, occurred_at, ...payload } = event;
    this.executionEvents.push({
      sequence,
      run_id,
      event_type: type,
      payload,
      occurred_at: occurred_at ?? new Date().toISOString(),
    });
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
      const args = String(toolInput?.['command'] ?? toolInput?.['args'] ?? '').trim();
      return args ? `kubectl ${args}` : 'kubectl';
    }
    if (Object.keys(toolInput ?? {}).length === 0) {
      return toolName;
    }
    return `${toolName}(${JSON.stringify(toolInput)})`;
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

  private updateScrollToLatestButton(): void {
    const messageList = this.messageListRef?.nativeElement;
    if (!messageList) return;
    const isScrollable = messageList.scrollHeight > messageList.clientHeight + 12;
    this.showScrollToLatest = isScrollable && !this.isNearMessageListBottom(messageList);
  }

  private isNearMessageListBottom(messageList: HTMLElement): boolean {
    return messageList.scrollTop + messageList.clientHeight >= messageList.scrollHeight - 48;
  }
}
