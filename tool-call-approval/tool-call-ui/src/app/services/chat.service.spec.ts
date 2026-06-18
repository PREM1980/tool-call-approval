import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ChatService } from './chat.service';

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
const EMPTY_SESSION = {
  session_id: null,
  instance_id: null,
  persona_id: null,
  persona_ids: [],
  system_prompt_id: null,
  model_id: null,
  provider: null,
};

describe('ChatService', () => {
  let service: ChatService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        ChatService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(ChatService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('posts a session envelope when creating a session', async () => {
    const promise = service.createSession(
      null,
      'persona-1',
      'prompt-1',
      'nemotron-3-super',
      'LOCAL',
      ['persona-1', 'persona-2'],
    );

    const req = httpMock.expectOne('/api/sessions');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      session: {
        session_id: null,
        instance_id: null,
        persona_id: 'persona-1',
        persona_ids: ['persona-1', 'persona-2'],
        system_prompt_id: 'prompt-1',
        model_id: 'nemotron-3-super',
        provider: 'LOCAL',
      },
      messages: [],
      approval: null,
    });
    req.flush({ session_id: 'abc-123' });

    await promise;
  });

  it('posts a message envelope when sending chat', async () => {
    service.setSession('abc-123');

    const promise = service.sendMessage([
      {
        role: 'user',
        content: 'hello',
        platform_context: { kubeconfig: 'apiVersion: v1' },
      },
    ]);

    const req = httpMock.expectOne('/api/sessions/abc-123/chat');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      session: { ...EMPTY_SESSION, session_id: 'abc-123' },
      messages: [
        {
          role: 'user',
          content: 'hello',
          data: EMPTY_DATA,
          timestamp: jasmine.any(String),
          user: null,
          agent: null,
          platform_context: {
            ...EMPTY_PLATFORM_CONTEXT,
            kubeconfig: 'apiVersion: v1',
          },
          ambient_context: EMPTY_AMBIENT_CONTEXT,
        },
      ],
      approval: null,
    });
    req.flush({ status: 'processing' });

    await promise;
  });

  it('updates session persona context for the next chat envelope without creating a session', async () => {
    service.setSession('abc-123');
    service.updateSessionContext({
      persona_id: 'persona-1',
      persona_ids: ['persona-1', 'persona-2'],
    });

    const promise = service.sendMessage([{ role: 'user', content: 'hello' }]);

    const req = httpMock.expectOne('/api/sessions/abc-123/chat');
    expect(req.request.method).toBe('POST');
    expect(req.request.body.session).toEqual({
      ...EMPTY_SESSION,
      session_id: 'abc-123',
      persona_id: 'persona-1',
      persona_ids: ['persona-1', 'persona-2'],
    });
    httpMock.expectNone('/api/sessions');
    req.flush({ status: 'processing' });

    await promise;
  });

  it('posts the ordered conversation transcript when sending chat', async () => {
    service.setSession('abc-123');

    const promise = service.sendMessage([
      { role: 'user', content: 'get pods' },
      { role: 'assistant', content: 'There are 2 pods.' },
      {
        role: 'user',
        content: 'get services',
        platform_context: { kubeconfig: 'apiVersion: v1' },
      },
    ]);

    const req = httpMock.expectOne('/api/sessions/abc-123/chat');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      session: { ...EMPTY_SESSION, session_id: 'abc-123' },
      messages: [
        {
          role: 'user',
          content: 'get pods',
          data: EMPTY_DATA,
          timestamp: jasmine.any(String),
          user: null,
          agent: null,
          platform_context: EMPTY_PLATFORM_CONTEXT,
          ambient_context: EMPTY_AMBIENT_CONTEXT,
        },
        {
          role: 'assistant',
          content: 'There are 2 pods.',
          data: EMPTY_DATA,
          timestamp: jasmine.any(String),
          user: null,
          agent: null,
        },
        {
          role: 'user',
          content: 'get services',
          data: EMPTY_DATA,
          timestamp: jasmine.any(String),
          user: null,
          agent: null,
          platform_context: {
            ...EMPTY_PLATFORM_CONTEXT,
            kubeconfig: 'apiVersion: v1',
          },
          ambient_context: EMPTY_AMBIENT_CONTEXT,
        },
      ],
      approval: null,
    });
    req.flush({ status: 'processing' });

    await promise;
  });

  it('posts an approval envelope when approving a tool', async () => {
    service.setSession('abc-123');

    const promise = service.approveTool('tool-1', true);

    const req = httpMock.expectOne('/api/sessions/abc-123/approve');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      session: { ...EMPTY_SESSION, session_id: 'abc-123' },
      messages: [],
      approval: {
        tool_use_id: 'tool-1',
        approved: true,
      },
    });
    req.flush({ status: 'ok' });

    await promise;
  });
});
