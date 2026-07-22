import { TestBed } from '@angular/core/testing';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { AuthService } from './auth.service';
import { authInterceptor } from './auth.interceptor';
import { HttpClient } from '@angular/common/http';

describe('AuthService', () => {
  let service: AuthService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    service = TestBed.inject(AuthService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.clear();
  });

  it('stores token and current user after login', async () => {
    const promise = service.login('admin', 'admin');

    const req = httpMock.expectOne('/api/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ username: 'admin', password: 'admin' });
    req.flush({
      access_token: 'token-123',
      token_type: 'bearer',
      user: { id: 'user-1', username: 'admin', role: 'admin' },
    });

    await promise;

    expect(service.accessToken()).toBe('token-123');
    expect(service.currentUser()?.username).toBe('admin');
    expect(localStorage.getItem('tool-call-auth-token')).toBe('token-123');
  });

  it('adds bearer token through the interceptor', () => {
    localStorage.setItem('tool-call-auth-token', 'token-123');
    localStorage.setItem(
      'tool-call-auth-user',
      JSON.stringify({ id: 'user-1', username: 'admin', role: 'admin' }),
    );
    TestBed.resetTestingModule();
    TestBed.configureTestingModule({
      providers: [
        AuthService,
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    const http = TestBed.inject(HttpClient);
    const mock = TestBed.inject(HttpTestingController);

    http.get('/api/sessions').subscribe();

    const req = mock.expectOne('/api/sessions');
    expect(req.request.headers.get('Authorization')).toBe('Bearer token-123');
    req.flush([]);
    mock.verify();
  });
});
