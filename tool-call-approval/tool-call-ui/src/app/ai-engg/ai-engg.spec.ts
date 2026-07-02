import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AiEngg } from './ai-engg';
import { Chat } from '../components/chat/chat';
import { Sessions } from './sessions/sessions';

@Component({
  selector: 'app-chat',
  standalone: true,
  template: '',
})
class ChatStub {
  @Input() resumeSessionId?: string | null;
}

@Component({
  selector: 'app-sessions',
  standalone: true,
  template: '',
})
class SessionsStub {
  @Output() openChat = new EventEmitter<string>();
}

describe('AiEngg', () => {
  async function setup(): Promise<ComponentFixture<AiEngg>> {
    await TestBed.configureTestingModule({
      imports: [AiEngg],
    })
      .overrideComponent(AiEngg, {
        remove: { imports: [Chat, Sessions] },
        add: { imports: [ChatStub, SessionsStub] },
      })
      .compileComponents();

    const fixture = TestBed.createComponent(AiEngg);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => TestBed.resetTestingModule());

  it('uses a high-contrast inactive Sessions tab treatment', async () => {
    const fixture = await setup();
    const sessionsTab = Array.from(
      fixture.nativeElement.querySelectorAll('.aiengg-tab'),
    ).find((tab) => (tab as HTMLElement).textContent?.trim() === 'Sessions') as HTMLElement;
    const styles = getComputedStyle(sessionsTab);

    expect(styles.backgroundColor).toBe('rgb(255, 255, 255)');
    expect(styles.borderColor).toBe('rgb(216, 225, 232)');
    expect(styles.color).toBe('rgb(19, 32, 51)');
  });

  it('uses a gray active tab treatment instead of blue', async () => {
    const fixture = await setup();
    const chatTab = Array.from(
      fixture.nativeElement.querySelectorAll('.aiengg-tab'),
    ).find((tab) => (tab as HTMLElement).textContent?.trim() === 'Chat') as HTMLElement;
    const styles = getComputedStyle(chatTab);

    expect(styles.backgroundColor).toBe('rgb(51, 65, 85)');
    expect(styles.borderColor).toBe('rgb(51, 65, 85)');
    expect(styles.color).toBe('rgb(255, 255, 255)');
  });
});
