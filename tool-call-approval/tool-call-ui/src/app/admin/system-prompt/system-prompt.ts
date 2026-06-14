import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService, SystemPromptData } from '../../services/admin.service';

@Component({
  selector: 'app-system-prompt',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './system-prompt.html',
  styleUrl: './system-prompt.css',
})
export class SystemPrompt implements OnInit {
  prompts: SystemPromptData[] = [];
  selected: SystemPromptData | null = null;
  isNew = false;
  form = { name: '', instructions: '' };
  saving = false;
  activating = false;
  error = '';

  constructor(private adminService: AdminService) {}

  async ngOnInit(): Promise<void> {
    this.prompts = await this.adminService.listSystemPrompts().catch(() => []);
  }

  startNew(): void {
    this.selected = null;
    this.isNew = true;
    this.form = { name: '', instructions: '' };
    this.error = '';
  }

  selectPrompt(prompt: SystemPromptData): void {
    this.selected = prompt;
    this.isNew = false;
    this.form = { name: prompt.name, instructions: prompt.instructions };
    this.error = '';
  }

  async save(): Promise<void> {
    if (this.saving) return;
    this.saving = true;
    this.error = '';
    try {
      if (this.isNew) {
        const created = await this.adminService.createSystemPrompt(this.form.name, this.form.instructions);
        this.prompts = await this.adminService.listSystemPrompts();
        this.selected = created;
        this.isNew = false;
        this.form = { name: created.name, instructions: created.instructions };
      } else if (this.selected) {
        const updated = await this.adminService.updateSystemPrompt(
          this.selected.id, this.form.name, this.form.instructions
        );
        this.prompts = await this.adminService.listSystemPrompts();
        this.selected = updated;
      }
    } catch (e: unknown) {
      const detail = (e as { error?: { detail?: string } })?.error?.detail;
      this.error = detail ?? 'Failed to save.';
    } finally {
      this.saving = false;
    }
  }

  async activate(prompt: SystemPromptData, event: Event): Promise<void> {
    event.stopPropagation();
    if (this.activating) return;
    this.activating = true;
    try {
      await this.adminService.activateSystemPrompt(prompt.id);
      this.prompts = await this.adminService.listSystemPrompts();
      if (this.selected?.id === prompt.id) {
        this.selected = this.prompts.find(p => p.id === prompt.id) ?? null;
      }
    } finally {
      this.activating = false;
    }
  }

  async deletePrompt(prompt: SystemPromptData, event: Event): Promise<void> {
    event.stopPropagation();
    await this.adminService.deleteSystemPrompt(prompt.id);
    this.prompts = await this.adminService.listSystemPrompts();
    if (this.selected?.id === prompt.id) {
      this.selected = null;
      this.isNew = false;
    }
  }

  get showForm(): boolean {
    return this.isNew || this.selected !== null;
  }

  get instructionLineCount(): number {
    if (!this.form.instructions) return 0;
    return this.form.instructions.split(/\r\n|\r|\n/).length;
  }

  get instructionLineCountLabel(): string {
    const count = this.instructionLineCount;
    return `${count} ${count === 1 ? 'line' : 'lines'}`;
  }

  get activePromptName(): string {
    return this.prompts.find(prompt => prompt.is_active)?.name ?? 'No active prompt';
  }
}
