import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService, PersonaData, Skill } from '../../services/admin.service';

@Component({
  selector: 'app-persona',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './persona.html',
  styleUrl: './persona.css',
})
export class Persona implements OnInit {
  personas: PersonaData[] = [];
  skills: Skill[] = [];
  selected: PersonaData | null = null;
  isNew = false;
  form = { name: '', skill_ids: [] as string[] };
  saving = false;
  error = '';

  constructor(private adminService: AdminService) {}

  async ngOnInit() {
    [this.personas, this.skills] = await Promise.all([
      this.adminService.getPersonas(),
      this.adminService.getSkills(),
    ]);
  }

  startNew() {
    this.selected = null;
    this.isNew = true;
    this.form = { name: '', skill_ids: [] };
    this.error = '';
  }

  selectPersona(persona: PersonaData) {
    this.selected = persona;
    this.isNew = false;
    this.form = { name: persona.name, skill_ids: [...persona.skill_ids] };
    this.error = '';
  }

  toggleSkill(id: string) {
    const idx = this.form.skill_ids.indexOf(id);
    if (idx >= 0) {
      this.form.skill_ids.splice(idx, 1);
    } else {
      this.form.skill_ids.push(id);
    }
  }

  isSkillSelected(id: string): boolean {
    return this.form.skill_ids.includes(id);
  }

  async save() {
    this.saving = true;
    this.error = '';
    try {
      if (this.isNew) {
        await this.adminService.createPersona(this.form.name, this.form.skill_ids);
      } else if (this.selected) {
        await this.adminService.updatePersona(
          this.selected.id,
          this.form.name,
          this.form.skill_ids,
        );
      }
      this.personas = await this.adminService.getPersonas();
      this.isNew = false;
      this.selected = null;
    } catch (e: unknown) {
      const detail = (e as { error?: { detail?: string } })?.error?.detail;
      this.error = detail ?? 'Failed to save persona';
    } finally {
      this.saving = false;
    }
  }

  async deletePersona(persona: PersonaData) {
    await this.adminService.deletePersona(persona.id);
    this.personas = await this.adminService.getPersonas();
    if (this.selected?.id === persona.id) this.selected = null;
  }

  get showForm(): boolean {
    return this.isNew || this.selected !== null;
  }
}
