import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToolCall } from '../../models/types';

@Component({
  selector: 'app-tool-approval',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './tool-approval.html',
  styleUrl: './tool-approval.css',
})
export class ToolApproval {
  @Input() toolCall!: ToolCall;
  @Input() disabled = false;
  @Output() approved = new EventEmitter<boolean>();

  get formattedCommand(): string {
    if (this.toolCall.tool_name === 'kubectl') {
      return `kubectl ${this.toolCall.tool_input['args']}`;
    }
    const firstVal = Object.values(this.toolCall.tool_input)[0];
    return `${this.toolCall.tool_name}: ${firstVal}`;
  }

  approve(): void {
    this.approved.emit(true);
  }

  reject(): void {
    this.approved.emit(false);
  }
}
