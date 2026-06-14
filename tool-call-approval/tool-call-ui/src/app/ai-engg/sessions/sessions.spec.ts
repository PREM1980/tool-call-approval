import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Sessions } from './sessions';
import { SessionsService } from '../../services/sessions.service';
import { ChatMessage, SessionSummary } from '../../models/types';

function makeSession(overrides: Partial<SessionSummary> = {}): SessionSummary {
  return {
    session_id: 'session-123456789',
    created_at: 1781400000,
    updated_at: 1781400300,
    turn_count: 1,
    first_message: 'check deployments',
    system_prompt_name: 'kubernetes_agent',
    ...overrides,
  };
}

function makeSessionsService(history: ChatMessage[] = []) {
  return {
    getAll: () => Promise.resolve([makeSession()]),
    getHistory: () => Promise.resolve(history),
  };
}

describe('Sessions', () => {
  afterEach(() => TestBed.resetTestingModule());

  async function setup(history: ChatMessage[] = []): Promise<ComponentFixture<Sessions>> {
    await TestBed.configureTestingModule({
      imports: [Sessions],
      providers: [{ provide: SessionsService, useValue: makeSessionsService(history) }],
    }).compileComponents();

    const fixture = TestBed.createComponent(Sessions);
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();
    return fixture;
  }

  it('renders assistant markdown tables as readable tables in session history', async () => {
    const fixture = await setup([
      { role: 'user', content: 'check deployments' },
      {
        role: 'assistant',
        content: [
          '## Deployment Status',
          '',
          '| Deployment | Ready | Image |',
          '|---|---:|---|',
          '| argocd-server | 1/1 | quay.io/argoproj/argocd:v3.4.3 |',
        ].join('\n'),
      },
    ]);

    fixture.debugElement.query(By.css('.session-row')).nativeElement.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const table = fixture.nativeElement.querySelector('.hist-table') as HTMLTableElement | null;
    const heading = fixture.nativeElement.querySelector('.hist-heading') as HTMLElement | null;

    expect(heading?.textContent?.trim()).toBe('Deployment Status');
    expect(table).toBeTruthy();
    expect(table?.querySelectorAll('th').length).toBe(3);
    expect(table?.textContent).toContain('argocd-server');
    expect(table?.textContent).toContain('quay.io/argoproj/argocd:v3.4.3');
  });
});
