import { TestBed } from '@angular/core/testing';
import { App } from './app';
import { ChatService } from './services/chat.service';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { Subject } from 'rxjs';
import { SseEvent } from './models/types';

describe('App', () => {
  let chatService: jasmine.SpyObj<ChatService>;

  beforeEach(async () => {
    const sseSubject = new Subject<SseEvent>();
    chatService = jasmine.createSpyObj(
      'ChatService',
      ['createSession', 'connectStream', 'sendMessage', 'approveTool', 'closeStream'],
      { sseEvents$: sseSubject }
    );
    chatService.createSession.and.returnValue(Promise.resolve());

    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        { provide: ChatService, useValue: chatService },
      ],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should render the router outlet', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).toBeTruthy();
  });
});
