import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { AiEngg } from './ai-engg';
import { Chat } from '../components/chat/chat';
import { SessionsService } from '../services/sessions.service';

@Component({
  selector: 'app-chat',
  standalone: true,
  template: '',
})
class ChatStub {
  @Input() resumeSessionId?: string | null;
  @Output() sessionChanged = new EventEmitter<void>();
}

describe('AiEngg', () => {
  async function setup(): Promise<ComponentFixture<AiEngg>> {
    await TestBed.configureTestingModule({
      imports: [AiEngg],
      providers: [{ provide: SessionsService, useValue: { getAll: () => Promise.resolve([]) } }],
    })
      .overrideComponent(AiEngg, {
        remove: { imports: [Chat] },
        add: { imports: [ChatStub] },
      })
      .compileComponents();

    const fixture = TestBed.createComponent(AiEngg);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => TestBed.resetTestingModule());

  it('renders the conversation rail', async () => {
    const fixture = await setup();
    expect(fixture.nativeElement.querySelector('.conversation-rail')).not.toBeNull();
  });

  it('provides a new chat action', async () => {
    const fixture = await setup();
    expect(fixture.nativeElement.querySelector('.new-chat-button')).not.toBeNull();
  });
});
