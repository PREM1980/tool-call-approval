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

  it('uses light panel styling for the sessions content', async () => {
    const fixture = await setup();
    const list = fixture.nativeElement.querySelector('.sessions-list') as HTMLElement;
    const header = fixture.nativeElement.querySelector('.sessions-header') as HTMLElement;
    const row = fixture.nativeElement.querySelector('.session-row') as HTMLElement;
    const listStyles = getComputedStyle(list);
    const headerStyles = getComputedStyle(header);
    const rowStyles = getComputedStyle(row);

    expect(listStyles.backgroundColor).toBe('rgb(255, 255, 255)');
    expect(listStyles.borderColor).toBe('rgb(216, 225, 232)');
    expect(headerStyles.color).toBe('rgb(19, 32, 51)');
    expect(rowStyles.backgroundColor).toBe('rgb(255, 255, 255)');
    expect(rowStyles.borderColor).toBe('rgb(228, 235, 241)');
  });

  it('uses gray accents for the selected session history instead of blue', async () => {
    const fixture = await setup([{ role: 'user', content: 'check deployments' }]);

    fixture.debugElement.query(By.css('.session-row')).nativeElement.click();
    fixture.detectChanges();
    await fixture.whenStable();
    fixture.detectChanges();

    const row = fixture.nativeElement.querySelector('.session-row.active') as HTMLElement;
    const history = fixture.nativeElement.querySelector('.session-history') as HTMLElement;
    const id = fixture.nativeElement.querySelector('.session-id') as HTMLElement;
    const button = fixture.nativeElement.querySelector('.continue-btn') as HTMLElement;
    const userBubble = fixture.nativeElement.querySelector('.hist-user .hist-bubble') as HTMLElement;

    expect(getComputedStyle(row).backgroundColor).toBe('rgb(241, 245, 249)');
    expect(getComputedStyle(row).borderColor).toBe('rgb(148, 163, 184)');
    expect(getComputedStyle(history).borderColor).toContain('rgb(148, 163, 184)');
    expect(getComputedStyle(id).color).toBe('rgb(51, 65, 85)');
    expect(getComputedStyle(button).backgroundColor).toBe('rgb(51, 65, 85)');
    expect(getComputedStyle(userBubble).backgroundColor).toBe('rgb(51, 65, 85)');
  });

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
