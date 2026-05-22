import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Chat } from '../components/chat/chat';
import { Sessions } from './sessions/sessions';

@Component({
  selector: 'app-ai-engg',
  standalone: true,
  imports: [CommonModule, Chat, Sessions],
  templateUrl: './ai-engg.html',
  styleUrl: './ai-engg.css',
})
export class AiEngg {
  tab: 'chat' | 'sessions' = 'chat';
}
