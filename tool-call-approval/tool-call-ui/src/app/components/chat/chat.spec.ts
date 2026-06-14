import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Chat } from './chat';
import { ChatService } from '../../services/chat.service';
import { AdminService, AgentInstance, SystemPromptData } from '../../services/admin.service';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { SseEvent } from '../../models/types';

describe('Chat', () => {
  let component: Chat;
  let fixture: ComponentFixture<Chat>;
  let chatService: jasmine.SpyObj<ChatService>;
  let adminService: jasmine.SpyObj<AdminService>;
  let sseSubject: Subject<SseEvent>;

  beforeEach(async () => {
    sseSubject = new Subject<SseEvent>();
    chatService = jasmine.createSpyObj(
      'ChatService',
      ['createSession', 'connectStream', 'sendMessage', 'approveTool', 'closeStream'],
      { sseEvents$: sseSubject }
    );
    chatService.createSession.and.returnValue(Promise.resolve());
    chatService.sendMessage.and.returnValue(Promise.resolve());
    chatService.approveTool.and.returnValue(Promise.resolve());

    adminService = jasmine.createSpyObj('AdminService', [
      'getAllAgentInstances',
      'getCredentials',
      'listSystemPrompts',
    ]);
    adminService.getAllAgentInstances.and.returnValue(Promise.resolve([]));
    adminService.getCredentials.and.returnValue(Promise.resolve(null));
    adminService.listSystemPrompts.and.returnValue(Promise.resolve([]));

    await TestBed.configureTestingModule({
      imports: [Chat],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ChatService, useValue: chatService },
        { provide: AdminService, useValue: adminService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Chat);
    component = fixture.componentInstance;
    fixture.detectChanges();
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize a session on init', () => {
    expect(chatService.createSession).toHaveBeenCalled();
  });

  it('should fetch all agent instances on init', () => {
    expect(adminService.getAllAgentInstances).toHaveBeenCalled();
  });

  it('should fetch system prompts on init', () => {
    expect(adminService.listSystemPrompts).toHaveBeenCalled();
  });

  it('should populate prompts and select the active prompt on init', async () => {
    const prompts: SystemPromptData[] = [
      {
        id: 'prompt-1',
        name: 'default',
        instructions: 'default instructions',
        is_active: false,
        created_at: '',
        updated_at: '',
      },
      {
        id: 'prompt-2',
        name: 'kubernetes_agent',
        instructions: 'kubernetes instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    adminService.listSystemPrompts.and.returnValue(Promise.resolve(prompts));
    await component.ngOnInit();
    expect(component.systemPrompts).toEqual(prompts);
    expect(component.selectedSystemPromptId).toBe('prompt-2');
  });

  it('should label the selected system prompt instead of the admin default in chat', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: false,
        created_at: '',
        updated_at: '',
      },
      {
        id: 'prompt-2',
        name: 'kubernetes_agent',
        instructions: 'kubernetes instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedSystemPromptId = 'prompt-1';
    fixture.detectChanges();

    const selected = fixture.nativeElement.querySelector(
      '.prompt-item[aria-selected="true"] .prompt-badge'
    ) as HTMLElement | null;
    const kubernetesButton = Array.from(
      fixture.nativeElement.querySelectorAll('.prompt-item')
    ).find(button => (button as HTMLElement).textContent?.includes('kubernetes_agent')) as HTMLElement | undefined;

    expect(selected?.textContent?.trim()).toBe('Selected');
    expect(kubernetesButton?.textContent).not.toContain('Active');
  });

  it('should show generic try-asking suggestions for default_agent', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: false,
        created_at: '',
        updated_at: '',
      },
      {
        id: 'prompt-2',
        name: 'kubernetes_agent',
        instructions: 'kubernetes instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedSystemPromptId = 'prompt-1';
    component.messages = [];
    fixture.detectChanges();

    const suggestions = Array.from(
      fixture.nativeElement.querySelectorAll('.suggestion-chip')
    ).map(el => (el as HTMLElement).textContent?.trim());

    expect(suggestions).toContain('"Summarize this text in three bullet points"');
    expect(suggestions.join(' ')).not.toContain('pods');
    expect(suggestions.join(' ')).not.toContain('Kubernetes');
  });

  it('should show Kubernetes try-asking suggestions for kubernetes_agent', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: false,
        created_at: '',
        updated_at: '',
      },
      {
        id: 'prompt-2',
        name: 'kubernetes_agent',
        instructions: 'kubernetes instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedSystemPromptId = 'prompt-2';
    component.messages = [];
    fixture.detectChanges();

    const suggestions = Array.from(
      fixture.nativeElement.querySelectorAll('.suggestion-chip')
    ).map(el => (el as HTMLElement).textContent?.trim());

    expect(suggestions).toContain('"List all pods in the default namespace"');
  });

  it('should populate instances and select first on init', async () => {
    const instances: AgentInstance[] = [
      {
        id: 'inst-1',
        agent_name: 'agent-a',
        instance_name: 'one',
        persona_id: null,
        mcp_positions: [],
        created_at: '',
        updated_at: '',
      },
    ];
    adminService.getAllAgentInstances.and.returnValue(Promise.resolve(instances));
    await component.ngOnInit();
    expect(component.instances).toEqual(instances);
    expect(component.selectedInstanceId).toBe('inst-1');
  });

  it('should set selectedInstanceId to null when no instances exist', async () => {
    adminService.getAllAgentInstances.and.returnValue(Promise.resolve([]));
    await component.ngOnInit();
    expect(component.selectedInstanceId).toBeNull();
  });

  it('should call newSession when onInstanceChange is called', async () => {
    spyOn(component, 'newSession').and.returnValue(Promise.resolve());
    await component.onInstanceChange();
    expect(component.newSession).toHaveBeenCalled();
  });

  it('should pass selectedInstanceId to createSession', async () => {
    component.selectedInstanceId = 'inst-42';
    component.selectedSystemPromptId = 'prompt-42';
    await component.newSession();
    expect(chatService.createSession).toHaveBeenCalledWith('inst-42', 'prompt-42');
  });

  it('should pass undefined to createSession when selections are null', async () => {
    component.selectedInstanceId = null;
    component.selectedSystemPromptId = null;
    await component.newSession();
    expect(chatService.createSession).toHaveBeenCalledWith(undefined, undefined);
  });

  it('should add a user message when sendMessage is called', async () => {
    component.userInput = 'Hello';
    await component.sendMessage();
    const userMsg = component.messages.find((m) => m.role === 'user');
    expect(userMsg?.content).toBe('Hello');
    expect(component.userInput).toBe('');
  });

  it('should stop waiting and show an error when sendMessage fails', async () => {
    chatService.sendMessage.and.returnValue(Promise.reject({
      status: 404,
      error: { detail: 'Session not found' },
    }));
    component.userInput = 'check argo cd deployments';

    await component.sendMessage();

    expect(component.isWaiting).toBeFalse();
    expect(component.messages.at(-1)?.role).toBe('system');
    expect(component.messages.at(-1)?.content).toContain('Session not found');
  });

  it('should not send empty messages', async () => {
    component.userInput = '   ';
    await component.sendMessage();
    expect(chatService.sendMessage).not.toHaveBeenCalled();
  });

  it('should add assistant message on SSE message event', () => {
    sseSubject.next({ type: 'message', content: 'Hi there!' });
    fixture.detectChanges();
    const assistantMsg = component.messages.find((m) => m.role === 'assistant');
    expect(assistantMsg?.content).toBe('Hi there!');
  });

  it('should stop waiting when the event stream is lost mid-response', () => {
    component.isWaiting = true;

    sseSubject.next({ type: 'stream_error', content: 'Stream connection lost.' });
    fixture.detectChanges();

    expect(component.isWaiting).toBeFalse();
    expect(component.messages.at(-1)?.role).toBe('system');
    expect(component.messages.at(-1)?.content).toContain('Stream connection lost.');
  });

  it('should add to pendingToolCalls on tool_call_pending event', () => {
    sseSubject.next({
      type: 'tool_call_pending',
      tool_use_id: 'abc',
      tool_name: 'calculate',
      tool_input: { expression: '2+2' },
    });
    fixture.detectChanges();
    expect(component.pendingToolCalls.length).toBe(1);
    expect(component.pendingToolCalls[0].tool_name).toBe('calculate');
  });

  it('should remove tool call from pendingToolCalls after approval', async () => {
    component.pendingToolCalls = [{
      tool_use_id: 'abc',
      tool_name: 'calculate',
      tool_input: { expression: '2+2' },
    }];
    await component.handleApproval('abc', true);
    expect(chatService.approveTool).toHaveBeenCalledWith('abc', true);
    expect(component.pendingToolCalls.length).toBe(0);
  });
});
