import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApprovalDecision, ToolCall } from '../../models/types';

@Component({
  selector: 'app-tool-approval',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './tool-approval.html',
  styleUrl: './tool-approval.css',
})
export class ToolApproval implements OnChanges {
  @Input() toolCall!: ToolCall;
  @Input() disabled = false;
  @Output() approved = new EventEmitter<ApprovalDecision>();
  editableInput: Record<string, unknown> = {};

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['toolCall']) {
      this.editableInput = { ...this.toolCall.tool_input };
    }
  }

  get parameters(): Array<{ key: string; value: unknown }> {
    return Object.entries(this.editableInput).map(([key, value]) => ({ key, value }));
  }

  get formattedCommand(): string {
    if (this.toolCall.tool_name === 'set_namespace') {
      const namespace = this.toolCall.tool_input['namespace'];
      return namespace === '__all__'
        ? 'Set active namespace to all namespaces'
        : `Set active namespace to ${namespace ?? ''}`.trim();
    }
    if (this.toolCall.tool_name === 'kubectl') {
      return `kubectl ${this.toolCall.tool_input['command'] ?? this.toolCall.tool_input['args'] ?? ''}`.trim();
    }
    const firstVal = Object.values(this.toolCall.tool_input)[0];
    return `${this.toolCall.tool_name}: ${firstVal}`;
  }

  approve(): void {
    this.approved.emit({ approved: true, tool_input: { ...this.editableInput } });
  }

  reject(): void {
    this.approved.emit({ approved: false, tool_input: { ...this.editableInput } });
  }
}
