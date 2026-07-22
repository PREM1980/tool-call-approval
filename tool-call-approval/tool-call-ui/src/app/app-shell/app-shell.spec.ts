import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { AppShell } from './app-shell';
import { AuthService } from '../services/auth.service';

describe('AppShell', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('labels the configuration area as Config instead of another Admin control', async () => {
    await TestBed.configureTestingModule({
      imports: [AppShell],
      providers: [
        provideRouter([]),
        {
          provide: AuthService,
          useValue: {
            isAdmin: () => true,
            currentUser: () => ({ id: 'user-1', username: 'admin', role: 'admin' }),
            logout: jasmine.createSpy('logout'),
          },
        },
      ],
    }).compileComponents();

    const fixture = TestBed.createComponent(AppShell);
    fixture.detectChanges();

    const links = Array.from(
      fixture.nativeElement.querySelectorAll('.topbar-link'),
      (link) => (link as HTMLElement).textContent?.trim(),
    );

    expect(links).toContain('Users');
    expect(links).toContain('Config');
    expect(links).not.toContain('Admin');
    expect(fixture.nativeElement.querySelector('.topbar-user')?.textContent.trim()).toBe('admin');
  });
});
