import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Chat } from './chat';
import { ChatService } from '../../services/chat.service';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { provideHttpClient } from '@angular/common/http';
import { Subject } from 'rxjs';
import { SseEvent } from '../../models/types';

describe('Chat', () => {
  let component: Chat;
  let fixture: ComponentFixture<Chat>;
  let chatService: jasmine.SpyObj<ChatService>;
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

    await TestBed.configureTestingModule({
      imports: [Chat],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ChatService, useValue: chatService },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(Chat);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should initialize a session on init', () => {
    expect(chatService.createSession).toHaveBeenCalled();
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
