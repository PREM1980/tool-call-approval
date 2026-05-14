import { Component } from '@angular/core';
import { Chat } from './components/chat/chat';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [Chat],
  template: '<app-chat />',
  styles: [':host { display: block; height: 100vh; }'],
})
export class App {}
