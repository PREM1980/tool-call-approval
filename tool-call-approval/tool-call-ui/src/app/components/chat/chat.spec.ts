import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Chat } from './chat';
import { ChatService } from '../../services/chat.service';
import { AdminService, AgentInstance } from '../../services/admin.service';
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
    ]);
    adminService.getAllAgentInstances.and.returnValue(Promise.resolve([]));
    adminService.getCredentials.and.returnValue(Promise.resolve(null));

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
    await component.newSession();
    expect(chatService.createSession).toHaveBeenCalledWith('inst-42');
  });

  it('should pass undefined to createSession when selectedInstanceId is null', async () => {
    component.selectedInstanceId = null;
    await component.newSession();
    expect(chatService.createSession).toHaveBeenCalledWith(undefined);
  });

  it('should add a user message when sendMessage is called', async () => {
    component.userInput = 'Hello';
    await component.sendMessage();
    const userMsg = component.messages.find((m) => m.role === 'user');
    expect(userMsg?.content).toBe('Hello');
    expect(component.userInput).toBe('');
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

  it('should set pendingToolCall on tool_call_pending event', () => {
    sseSubject.next({
      type: 'tool_call_pending',
      tool_use_id: 'abc',
      tool_name: 'calculate',
      tool_input: { expression: '2+2' },
    });
    fixture.detectChanges();
    expect(component.pendingToolCall).not.toBeNull();
    expect(component.pendingToolCall?.tool_name).toBe('calculate');
  });

  it('should clear pendingToolCall after approval', async () => {
    component.pendingToolCall = {
      tool_use_id: 'abc',
      tool_name: 'calculate',
      tool_input: { expression: '2+2' },
    };
    await component.handleApproval(true);
    expect(chatService.approveTool).toHaveBeenCalledWith(true);
    expect(component.pendingToolCall).toBeNull();
  });
});
