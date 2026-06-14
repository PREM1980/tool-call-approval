import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { SystemPrompt } from './system-prompt';
import { AdminService } from '../../services/admin.service';

function makeAdminService() {
  return {
    listSystemPrompts: () => Promise.resolve([]),
    createSystemPrompt: () => Promise.resolve(null),
    updateSystemPrompt: () => Promise.resolve(null),
    deleteSystemPrompt: () => Promise.resolve(),
    activateSystemPrompt: () => Promise.resolve(null),
  };
}

describe('SystemPrompt', () => {
  let fixture: ComponentFixture<SystemPrompt>;

  beforeEach(fakeAsync(() => {
    TestBed.configureTestingModule({
      imports: [SystemPrompt],
      providers: [{ provide: AdminService, useValue: makeAdminService() }],
    }).compileComponents();

    fixture = TestBed.createComponent(SystemPrompt);
    fixture.detectChanges();
    tick();
    fixture.detectChanges();
  }));

  afterEach(() => TestBed.resetTestingModule());

  it('renders a bounded prompt workspace with page heading', () => {
    const shell = fixture.nativeElement.querySelector('.sp-shell');
    const title = fixture.nativeElement.querySelector('.sp-page-title');

    expect(shell).toBeTruthy();
    expect(title?.textContent.trim()).toBe('System Prompt Studio');
  });

  it('opens the editor when creating a new prompt', fakeAsync(() => {
    fixture.debugElement.query(By.css('.sp-new-btn')).nativeElement.click();
    tick();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.sp-name-input')).toBeTruthy();
    expect(fixture.nativeElement.querySelector('.sp-textarea')).toBeTruthy();
  }));

  it('shows a readable empty-editor line count', fakeAsync(() => {
    fixture.debugElement.query(By.css('.sp-new-btn')).nativeElement.click();
    tick();
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.sp-line-count').textContent.trim()).toBe('0 lines');
  }));
});
