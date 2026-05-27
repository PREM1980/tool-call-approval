import { ComponentFixture, TestBed, fakeAsync, tick, discardPeriodicTasks } from '@angular/core/testing';
import { AgentList } from './agent-list';
import { AgentsService } from '../../../services/agents.service';

const RUNNING = { name: 'alpha-agent', namespace: 'default', image: 'alpha:latest', replicas: 2, ready_replicas: 2, status: 'Running' };
const PENDING = { name: 'beta-agent',  namespace: 'staging', image: 'beta:v1',     replicas: 1, ready_replicas: 0, status: 'Pending' };
const FAILED  = { name: 'gamma-agent', namespace: 'prod',    image: 'gamma:v2',    replicas: 1, ready_replicas: 0, status: 'Failed'  };

function makeService(agents: any[] = []) {
  return { list: () => Promise.resolve(agents), scale: () => Promise.resolve(), restart: () => Promise.resolve(), delete: () => Promise.resolve() };
}

function setupFixture(agents: any[]): { get: () => ComponentFixture<AgentList> } {
  const ref = { fixture: null as unknown as ComponentFixture<AgentList> };
  beforeEach(fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [AgentList],
      providers: [{ provide: AgentsService, useValue: makeService(agents) }],
    }).compileComponents();
    ref.fixture = TestBed.createComponent(AgentList);
    ref.fixture.detectChanges();
    tick();
    ref.fixture.detectChanges();
  }));
  afterEach(fakeAsync(() => discardPeriodicTasks()));
  return { get: () => ref.fixture };
}

describe('AgentList — empty', () => {
  const { get } = setupFixture([]);
  afterEach(() => TestBed.resetTestingModule());

  it('shows empty state', () => {
    expect(get().nativeElement.querySelector('.agent-empty')).toBeTruthy();
    expect(get().nativeElement.querySelector('.agent-row')).toBeNull();
  });
});

describe('AgentList — with agents', () => {
  const { get } = setupFixture([RUNNING, PENDING, FAILED]);
  afterEach(() => TestBed.resetTestingModule());

  it('renders one row per agent', () => {
    expect(get().nativeElement.querySelectorAll('.agent-row').length).toBe(3);
  });

  it('stat card shows correct running count', () => {
    const cards = get().nativeElement.querySelectorAll('.stat-card');
    expect(cards[0].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('stat card shows correct total count', () => {
    const cards = get().nativeElement.querySelectorAll('.stat-card');
    expect(cards[1].querySelector('.stat-num').textContent.trim()).toBe('3');
  });

  it('stat card shows correct pending count', () => {
    const cards = get().nativeElement.querySelectorAll('.stat-card');
    expect(cards[2].querySelector('.stat-num').textContent.trim()).toBe('1');
  });

  it('stat card shows correct failed count', () => {
    const cards = get().nativeElement.querySelectorAll('.stat-card');
    expect(cards[3].querySelector('.stat-num').textContent.trim()).toBe('1');
  });
});

describe('AgentList — status badges', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('Running row has running status badge', fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [AgentList],
      providers: [{ provide: AgentsService, useValue: makeService([RUNNING]) }],
    }).compileComponents();
    const f = TestBed.createComponent(AgentList);
    f.detectChanges(); tick(); f.detectChanges();
    const badge = f.nativeElement.querySelector('.status-badge');
    expect(badge.classList).toContain('running');
    expect(badge.textContent).toContain('Running');
    discardPeriodicTasks();
  }));

  it('Pending row has pending status badge', fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [AgentList],
      providers: [{ provide: AgentsService, useValue: makeService([PENDING]) }],
    }).compileComponents();
    const f = TestBed.createComponent(AgentList);
    f.detectChanges(); tick(); f.detectChanges();
    expect(f.nativeElement.querySelector('.status-badge').classList).toContain('pending');
    discardPeriodicTasks();
  }));

  it('Failed row has failed status badge', fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [AgentList],
      providers: [{ provide: AgentsService, useValue: makeService([FAILED]) }],
    }).compileComponents();
    const f = TestBed.createComponent(AgentList);
    f.detectChanges(); tick(); f.detectChanges();
    expect(f.nativeElement.querySelector('.status-badge').classList).toContain('failed');
    discardPeriodicTasks();
  }));

  it('shows agent name and namespace pill', fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [AgentList],
      providers: [{ provide: AgentsService, useValue: makeService([RUNNING]) }],
    }).compileComponents();
    const f = TestBed.createComponent(AgentList);
    f.detectChanges(); tick(); f.detectChanges();
    const row = f.nativeElement.querySelector('.agent-row');
    expect(row.querySelector('.agent-name').textContent.trim()).toBe('alpha-agent');
    expect(row.querySelector('.agent-ns').textContent.trim()).toBe('default');
    discardPeriodicTasks();
  }));

  it('shows replica count', fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [AgentList],
      providers: [{ provide: AgentsService, useValue: makeService([RUNNING]) }],
    }).compileComponents();
    const f = TestBed.createComponent(AgentList);
    f.detectChanges(); tick(); f.detectChanges();
    expect(f.nativeElement.querySelector('.rep-count').textContent.trim()).toBe('2');
    discardPeriodicTasks();
  }));
});
