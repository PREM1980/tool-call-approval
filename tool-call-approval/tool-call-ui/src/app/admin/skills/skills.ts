import { Component, OnInit } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { AdminService, Skill } from '../../services/admin.service';

@Component({
  selector: 'app-skills',
  standalone: true,
  imports: [CommonModule, DatePipe],
  templateUrl: './skills.html',
  styleUrl: './skills.css',
})
export class Skills implements OnInit {
  skills: Skill[] = [];
  uploading = false;
  error = '';

  constructor(private adminService: AdminService) {}

  async ngOnInit() {
    await this.load();
  }

  async load() {
    this.skills = await this.adminService.getSkills();
  }

  async onFile(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (!file) return;
    this.uploading = true;
    this.error = '';
    try {
      await this.adminService.uploadSkill(file);
      await this.load();
      (event.target as HTMLInputElement).value = '';
    } catch {
      this.error = 'Upload failed';
    } finally {
      this.uploading = false;
    }
  }

  async delete(id: string) {
    await this.adminService.deleteSkill(id);
    await this.load();
  }
}
