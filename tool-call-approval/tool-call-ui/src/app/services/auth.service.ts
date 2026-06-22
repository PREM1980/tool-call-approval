import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

const API = '/api/auth';
const TOKEN_KEY = 'tool-call-auth-token';
const USER_KEY = 'tool-call-auth-user';

export type UserRole = 'admin' | 'user';

export interface AuthUser {
  id: string;
  username: string;
  role: UserRole;
}

export interface LoginResponse {
  access_token: string;
  token_type: 'bearer';
  user: AuthUser;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private tokenState = signal<string | null>(localStorage.getItem(TOKEN_KEY));
  private userState = signal<AuthUser | null>(this.loadStoredUser());

  readonly currentUser = computed(() => this.userState());
  readonly accessToken = computed(() => this.tokenState());
  readonly isAuthenticated = computed(() => !!this.tokenState() && !!this.userState());
  readonly isAdmin = computed(() => this.userState()?.role === 'admin');

  async login(username: string, password: string): Promise<AuthUser> {
    const response = await firstValueFrom(
      this.http.post<LoginResponse>(`${API}/login`, { username, password }),
    );
    this.setSession(response.access_token, response.user);
    return response.user;
  }

  async loadCurrentUser(): Promise<AuthUser | null> {
    if (!this.tokenState()) return null;
    const user = await firstValueFrom(this.http.get<AuthUser>(`${API}/me`));
    this.setSession(this.tokenState() as string, user);
    return user;
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    this.tokenState.set(null);
    this.userState.set(null);
  }

  private setSession(token: string, user: AuthUser): void {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    this.tokenState.set(token);
    this.userState.set(user);
  }

  private loadStoredUser(): AuthUser | null {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      const parsed = JSON.parse(raw) as AuthUser;
      if (!parsed.id || !parsed.username || !['admin', 'user'].includes(parsed.role)) {
        return null;
      }
      return parsed;
    } catch {
      return null;
    }
  }
}
