import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AgentList } from './agent-list';
import { AgentsService } from '../../../services/agents.service';

const RUNNING = { name: 'alpha-agent', namespace: 'default', image: 'alpha:latest', replicas: 2, ready_replicas: 2, status: 'Running' };
const PENDING = { name: 'beta-agent',  namespace: 'staging', image: 'beta:v1',     replicas: 1, ready_replicas: 0, status: 'Pending' };
const FAILED  = { name: 'gamma-agent', namespace: 'prod',    image: 'gamma:v2',    replicas: 1, ready_replicas: 0, status: 'Failed'  };

function makeService(agents: any[] = []) {
  return { list: () => Promise.resolve(agents), scale: () => Promise.resolve(), restart: () => Promise.resolve(), delete: () => Promise.resolve() };
}

async function build(agents: any[]) {
  await TestBed.configureTestingModule({
    imports: [AgentList],
    providers: [{ provide: AgentsService, useValue: makeService(agents) }],
  }).compileComponents();
  const fixture: ComponentFixture<AgentList> = TestBed.createComponent(AgentList);
  fixture.detectChanges();
  await fixture.whenStable();
  fixture.detectChanges();
  return fixture;
}

describe('AgentList', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('shows empty state when no agents', async () => {
    const f = await build([]);
    expect(f.nativeElement.querySelector('.agent-empty')).toBeTruthy();
    expect(f.nativeElement.querySelector('.agent-row')).toBeNull();
  });

  it('renders one row per agent', async () => {
    const f = await build([RUNNING, PENDING]);
    expect(f.nativeElement.querySelectorAll('.agent-row').length).toBe(2);
  });

  it('stat card shows correct running count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    // Running card is first
    expect(cards[0].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('stat card shows correct total count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    // Total card is second
    expect(cards[1].querySelector('.stat-num').textContent.trim()).toBe('3');
  });

  it('stat card shows correct pending count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    expect(cards[2].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('stat card shows correct failed count', async () => {
    const f = await build([RUNNING, PENDING, FAILED]);
    const cards = f.nativeElement.querySelectorAll('.stat-card');
    expect(cards[3].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('Running row has running status badge', async () => {
    const f = await build([RUNNING]);
    const badge = f.nativeElement.querySelector('.status-badge');
    expect(badge.classList).toContain('running');
    expect(badge.textContent).toContain('Running');
  });

  it('Pending row has pending status badge', async () => {
    const f = await build([PENDING]);
    const badge = f.nativeElement.querySelector('.status-badge');
    expect(badge.classList).toContain('pending');
  });

  it('Failed row has failed status badge', async () => {
    const f = await build([FAILED]);
    const badge = f.nativeElement.querySelector('.status-badge');
    expect(badge.classList).toContain('failed');
  });

  it('shows agent name and namespace pill', async () => {
    const f = await build([RUNNING]);
    const row = f.nativeElement.querySelector('.agent-row');
    expect(row.querySelector('.agent-name').textContent.trim()).toBe('alpha-agent');
    expect(row.querySelector('.agent-ns').textContent.trim()).toBe('default');
  });

  it('shows replica count', async () => {
    const f = await build([RUNNING]);
    expect(f.nativeElement.querySelector('.rep-count').textContent.trim()).toBe('2');
  });
});
