import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Chat } from './chat';
import { ChatService } from '../../services/chat.service';
import { AdminService, PersonaData, Skill, SystemPromptData } from '../../services/admin.service';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { SseEvent } from '../../models/types';

const EMPTY_DATA = {
  cmds: [],
  executed_cmds: [],
  url_configs: [],
  user_file_uploads: [],
};
const EMPTY_PLATFORM_CONTEXT = {
  k8s_namespace: null,
  duplo_base_url: null,
  duplo_token: null,
  tenant_name: null,
  aws_credentials: null,
  kubeconfig: null,
};
const EMPTY_AMBIENT_CONTEXT = { user_terminal_cmds: [] };

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
      ['createSession', 'connectStream', 'sendMessage', 'approveTool', 'closeStream', 'updateSessionContext'],
      { sseEvents$: sseSubject }
    );
    chatService.createSession.and.returnValue(Promise.resolve());
    chatService.sendMessage.and.returnValue(Promise.resolve());
    chatService.approveTool.and.returnValue(Promise.resolve());

    adminService = jasmine.createSpyObj('AdminService', [
      'getCredentials',
      'getPersonas',
      'getSkills',
      'listSystemPrompts',
    ]);
    adminService.getCredentials.and.returnValue(Promise.resolve(null));
    adminService.getPersonas.and.returnValue(Promise.resolve([]));
    adminService.getSkills.and.returnValue(Promise.resolve([]));
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

  it('should fetch personas on init', () => {
    expect(adminService.getPersonas).toHaveBeenCalled();
  });

  it('should fetch skills on init', () => {
    expect(adminService.getSkills).toHaveBeenCalled();
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

  it('should render context controls in the left sidebar instead of the top bar', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.personas = [
      {
        id: 'persona-1',
        name: 'ops_persona',
        skill_ids: [],
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedSystemPromptId = 'prompt-1';
    component.selectedPersonaIds = ['persona-1'];
    fixture.detectChanges();

    const sidebar = fixture.nativeElement.querySelector('.chat-sidebar') as HTMLElement | null;

    expect(sidebar?.querySelector('.prompt-picker')).toBeTruthy();
    expect(sidebar?.querySelector('.provider-picker')).toBeTruthy();
    expect(sidebar?.querySelector('#modelSelect')).toBeTruthy();
    expect(sidebar?.querySelector('.persona-list')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('.chat-topbar .prompt-picker')).toBeNull();
    expect(fixture.nativeElement.querySelector('.chat-topbar .provider-picker')).toBeNull();
  });

  it('should order provider and model before system prompt and personas in the sidebar', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.personas = [
      {
        id: 'persona-1',
        name: 'ops_persona',
        skill_ids: [],
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedProvider = 'LOCAL';
    fixture.detectChanges();

    const labels = Array.from(
      fixture.nativeElement.querySelectorAll('.chat-sidebar .context-label')
    ).map(label => (label as HTMLElement).textContent?.trim());

    expect(labels).toEqual(['Provider', 'Model', 'System prompt', 'Personas']);
  });

  it('should use generous vertical spacing between sidebar context groups', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedSystemPromptId = 'prompt-1';
    fixture.detectChanges();

    const sidebar = fixture.nativeElement.querySelector('.chat-sidebar') as HTMLElement;

    expect(getComputedStyle(sidebar).gap).toBe('30px');
  });

  it('should render sidebar section labels with stronger visual emphasis', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.personas = [
      {
        id: 'persona-1',
        name: 'ops_persona',
        skill_ids: [],
        created_at: '',
        updated_at: '',
      },
    ];
    fixture.detectChanges();

    const label = fixture.nativeElement.querySelector('.context-label') as HTMLElement;
    const styles = getComputedStyle(label);

    expect(styles.fontWeight).toBe('700');
    expect(styles.color).toBe('rgb(203, 213, 225)');
    expect(styles.textTransform).toBe('uppercase');
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

  it('should populate personas and select first on init', async () => {
    const personas: PersonaData[] = [
      {
        id: 'persona-1',
        name: 'ops_persona',
        skill_ids: ['skill-1'],
        created_at: '',
        updated_at: '',
      },
    ];
    adminService.getPersonas.and.returnValue(Promise.resolve(personas));
    await component.ngOnInit();
    expect(component.personas).toEqual(personas);
    expect(component.selectedPersonaIds).toEqual(['persona-1']);
  });

  it('should set selectedPersonaIds to empty when no personas exist', async () => {
    adminService.getPersonas.and.returnValue(Promise.resolve([]));
    await component.ngOnInit();
    expect(component.selectedPersonaIds).toEqual([]);
  });

  it('should show a personas empty state in the sidebar when no personas exist', () => {
    component.systemPrompts = [
      {
        id: 'prompt-1',
        name: 'default_agent',
        instructions: 'default instructions',
        is_active: true,
        created_at: '',
        updated_at: '',
      },
    ];
    component.personas = [];
    fixture.detectChanges();

    const sidebar = fixture.nativeElement.querySelector('.chat-sidebar') as HTMLElement | null;
    const personaPicker = sidebar?.querySelector('.persona-picker') as HTMLElement | null;

    expect(personaPicker).toBeTruthy();
    expect(personaPicker?.textContent).toContain('Personas');
    expect(personaPicker?.querySelector('.persona-empty')?.textContent).toContain('No personas configured');
  });

  it('should render personas as a multi-select checklist', () => {
    component.personas = [
      {
        id: 'persona-1',
        name: 'ops_persona',
        skill_ids: ['skill-1'],
        created_at: '',
        updated_at: '',
      },
      {
        id: 'persona-2',
        name: 'security_persona',
        skill_ids: ['skill-2'],
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedPersonaIds = ['persona-1', 'persona-2'];
    fixture.detectChanges();

    const personaItems = fixture.nativeElement.querySelectorAll('.persona-item');
    const checkedInputs = fixture.nativeElement.querySelectorAll('.persona-item input:checked');

    expect(personaItems.length).toBe(2);
    expect(checkedInputs.length).toBe(2);
    expect(fixture.nativeElement.querySelector('#personaSelect')).toBeNull();
  });

  it('should update persona context without creating a new session when a persona checkbox changes', async () => {
    spyOn(component, 'newSession').and.returnValue(Promise.resolve());
    component.personas = [
      { id: 'persona-1', name: 'ops_persona', skill_ids: [], created_at: '', updated_at: '' },
      { id: 'persona-2', name: 'security_persona', skill_ids: [], created_at: '', updated_at: '' },
    ];
    component.selectedPersonaIds = ['persona-1'];
    component.messages = [{
      id: 'msg-1',
      role: 'assistant',
      content: 'Existing conversation stays here.',
      timestamp: new Date(),
    }];
    chatService.createSession.calls.reset();

    await component.togglePersonaSelection('persona-2', true);

    expect(component.newSession).not.toHaveBeenCalled();
    expect(chatService.createSession).not.toHaveBeenCalled();
    expect(chatService.updateSessionContext).toHaveBeenCalledWith({
      persona_id: 'persona-1',
      persona_ids: ['persona-1', 'persona-2'],
    });
    expect(component.messages.length).toBe(1);
  });

  it('should add and remove persona ids when toggled', async () => {
    spyOn(component, 'newSession').and.returnValue(Promise.resolve());
    component.personas = [
      { id: 'persona-1', name: 'ops_persona', skill_ids: [], created_at: '', updated_at: '' },
      { id: 'persona-2', name: 'security_persona', skill_ids: [], created_at: '', updated_at: '' },
    ];
    component.selectedPersonaIds = ['persona-1'];

    await component.togglePersonaSelection('persona-2', true);
    expect(component.selectedPersonaIds).toEqual(['persona-1', 'persona-2']);

    await component.togglePersonaSelection('persona-1', false);
    expect(component.selectedPersonaIds).toEqual(['persona-2']);
  });

  it('should pass selectedPersonaIds to createSession', async () => {
    component.selectedPersonaIds = ['persona-42', 'persona-99'];
    component.selectedSystemPromptId = 'prompt-42';
    await component.newSession();
    expect(chatService.createSession).toHaveBeenCalledWith(
      null,
      'persona-42',
      'prompt-42',
      'nemotron-3-super',
      'LOCAL',
      ['persona-42', 'persona-99'],
    );
  });

  it('should pass undefined to createSession when selections are null', async () => {
    component.selectedPersonaIds = [];
    component.selectedSystemPromptId = null;
    await component.newSession();
    expect(chatService.createSession).toHaveBeenCalledWith(
      null,
      undefined,
      undefined,
      'nemotron-3-super',
      'LOCAL',
      [],
    );
  });

  it('should summarize selected persona skills across all selected personas', () => {
    const skills: Skill[] = [
      { id: 'skill-1', filename: 'ops.md', uploaded_at: '' },
      { id: 'skill-2', filename: 'deploy.md', uploaded_at: '' },
      { id: 'skill-3', filename: 'security.md', uploaded_at: '' },
    ];
    component.skills = skills;
    component.personas = [
      {
        id: 'persona-1',
        name: 'ops_persona',
        skill_ids: ['skill-1', 'skill-2'],
        created_at: '',
        updated_at: '',
      },
      {
        id: 'persona-2',
        name: 'security_persona',
        skill_ids: ['skill-2', 'skill-3'],
        created_at: '',
        updated_at: '',
      },
    ];
    component.selectedPersonaIds = ['persona-1', 'persona-2'];

    expect(component.selectedPersonaSkillSummary()).toBe('ops.md, deploy.md, security.md');
  });

  it('should add a user message when sendMessage is called', async () => {
    component.userInput = 'Hello';
    await component.sendMessage();
    const userMsg = component.messages.find((m) => m.role === 'user');
    expect(userMsg?.content).toBe('Hello');
    expect(component.userInput).toBe('');
  });

  it('should send the ordered user and assistant transcript in the request envelope', async () => {
    component.messages = [
      {
        id: 'msg-1',
        role: 'user',
        content: 'get pods',
        timestamp: new Date('2026-06-17T10:00:00Z'),
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content: 'There are 2 pods.',
        timestamp: new Date('2026-06-17T10:00:01Z'),
      },
    ];
    component.userInput = 'get services';

    await component.sendMessage();

    expect(chatService.sendMessage).toHaveBeenCalledWith([
      {
        role: 'user',
        content: 'get pods',
        data: EMPTY_DATA,
        timestamp: '2026-06-17T10:00:00.000Z',
        user: null,
        agent: null,
        platform_context: EMPTY_PLATFORM_CONTEXT,
        ambient_context: EMPTY_AMBIENT_CONTEXT,
      },
      {
        role: 'assistant',
        content: 'There are 2 pods.',
        data: EMPTY_DATA,
        timestamp: '2026-06-17T10:00:01.000Z',
        user: null,
        agent: null,
      },
      jasmine.objectContaining({
        role: 'user',
        content: 'get services',
        data: EMPTY_DATA,
        user: null,
        agent: null,
        platform_context: EMPTY_PLATFORM_CONTEXT,
        ambient_context: EMPTY_AMBIENT_CONTEXT,
      }),
    ]);
  });

  it('should include approved kubectl commands in the next request envelope', async () => {
    component.userInput = 'get namespaces';
    await component.sendMessage();
    chatService.sendMessage.calls.reset();

    sseSubject.next({
      type: 'tool_call_pending',
      tool_use_id: 'tool-1',
      tool_name: 'kubectl',
      tool_input: { args: 'get namespaces' },
    });
    await component.handleApproval('tool-1', true);
    sseSubject.next({
      type: 'tool_result',
      tool_use_id: 'tool-1',
      tool_name: 'kubectl',
      result: 'kubectl(args=get namespaces) completed in 0.25s',
    });
    sseSubject.next({
      type: 'message',
      content: 'Namespaces listed.',
    });

    component.userInput = 'get services';
    await component.sendMessage();

    const messages = chatService.sendMessage.calls.mostRecent().args[0];
    expect(messages[1]).toEqual(jasmine.objectContaining({
      role: 'assistant',
      content: 'Namespaces listed.',
      data: {
        cmds: [{ command: 'kubectl get namespaces', execute: true }],
        executed_cmds: [{
          command: 'kubectl get namespaces',
          output: 'kubectl(args=get namespaces) completed in 0.25s',
        }],
        url_configs: [],
        user_file_uploads: [],
      },
    }));
  });

  it('should include rejected kubectl commands in the next request envelope', async () => {
    component.userInput = 'delete namespace prod';
    await component.sendMessage();
    chatService.sendMessage.calls.reset();

    sseSubject.next({
      type: 'tool_call_pending',
      tool_use_id: 'tool-2',
      tool_name: 'kubectl',
      tool_input: { args: 'delete namespace prod' },
    });
    await component.handleApproval('tool-2', false);
    sseSubject.next({
      type: 'tool_rejected',
      tool_use_id: 'tool-2',
      tool_name: 'kubectl',
    });
    sseSubject.next({
      type: 'message',
      content: 'I did not run that command.',
    });

    component.userInput = 'get namespaces';
    await component.sendMessage();

    const messages = chatService.sendMessage.calls.mostRecent().args[0];
    expect(messages[1]).toEqual(jasmine.objectContaining({
      role: 'assistant',
      content: 'I did not run that command.',
      data: {
        cmds: [{
          command: 'kubectl delete namespace prod',
          execute: false,
          rejection_reason: 'User rejected tool call',
        }],
        executed_cmds: [],
        url_configs: [],
        user_file_uploads: [],
      },
    }));
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

  it('should not show internal skill instruction tool results as chat messages', () => {
    sseSubject.next({
      type: 'tool_result',
      tool_use_id: 'skill-tool-1',
      tool_name: 'get_skill_instructions',
      result: 'get_skill_instructions(skill_name=kubernetes-report-formatter) completed in 0.0006s',
    });
    fixture.detectChanges();

    expect(component.messages.some(message =>
      message.content.includes('get_skill_instructions')
    )).toBeFalse();
  });

  it('should split a glued report summary heading before rendering markdown', () => {
    component.messages = [{
      id: 'msg-1',
      role: 'assistant',
      content: '# Cluster Status ReportSummary: The cluster is healthy.',
      timestamp: new Date(),
    }];
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('.msg-heading') as HTMLElement | null;
    const paragraph = fixture.nativeElement.querySelector('.msg-paragraph') as HTMLElement | null;

    expect(heading?.textContent?.trim()).toBe('Cluster Status Report');
    expect(paragraph?.textContent).toContain('Summary: The cluster is healthy.');
  });

  it('should render glued cluster reports as scoped chat blocks', () => {
    component.messages = [{
      id: 'msg-1',
      role: 'assistant',
      content: ' # Cluster Status ReportSummary: The cluster consists of3 nodes. There are13 namespaces.',
      timestamp: new Date(),
    }];
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('.msg-heading') as HTMLElement | null;
    const paragraph = fixture.nativeElement.querySelector('.msg-paragraph') as HTMLElement | null;

    expect(heading?.textContent?.trim()).toBe('Cluster Status Report');
    expect(paragraph?.textContent?.trim()).toBe(
      'Summary: The cluster consists of 3 nodes. There are 13 namespaces.',
    );
  });

  it('should split glued Kubernetes section status text before rendering markdown', () => {
    component.messages = [{
      id: 'msg-1',
      role: 'assistant',
      content: '# Node StatusAll 3 nodes are in Ready state.\n\n| Node | Status |\n|---|---|\n| node-1 | Ready |',
      timestamp: new Date(),
    }];
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('.msg-heading') as HTMLElement | null;
    const paragraph = fixture.nativeElement.querySelector('.msg-paragraph') as HTMLElement | null;
    const table = fixture.nativeElement.querySelector('.msg-table') as HTMLElement | null;

    expect(heading?.textContent?.trim()).toBe('Node Status');
    expect(paragraph?.textContent?.trim()).toBe('All 3 nodes are in Ready state.');
    expect(table).toBeTruthy();
  });

  it('should keep rendered markdown headings compact inside assistant bubbles', () => {
    component.messages = [{
      id: 'msg-1',
      role: 'assistant',
      content: '# Cluster Status Report\n\n**Summary:** The cluster is healthy.',
      timestamp: new Date(),
    }];
    fixture.detectChanges();

    const heading = fixture.nativeElement.querySelector('.msg-heading') as HTMLElement | null;

    expect(heading).toBeTruthy();
    expect(parseFloat(getComputedStyle(heading!).fontSize)).toBeLessThan(24);
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
