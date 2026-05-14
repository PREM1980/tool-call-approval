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

  get formattedInput(): string {
    return JSON.stringify(this.toolCall.tool_input, null, 2);
  }

  approve(): void {
    this.approved.emit(true);
  }

  reject(): void {
    this.approved.emit(false);
  }
}
