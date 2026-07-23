import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService } from '../../services/admin.service';

@Component({
  selector: 'app-credentials',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './credentials.html',
  styleUrl: './credentials.css',
})
export class Credentials implements OnInit {
  form = {
    kubeconfig: '',
  };
  saving = false;
  saved = false;
  error = '';

  constructor(private adminService: AdminService) {}

  async ngOnInit() {
    const creds = await this.adminService.getCredentials();
    if (creds) {
      this.form.kubeconfig = creds.kubeconfig ?? '';
    }
  }

  async onKubeconfigFile(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0];
    if (file) this.form.kubeconfig = await file.text();
  }

  async save() {
    this.saving = true;
    this.saved = false;
    this.error = '';
    try {
      await this.adminService.saveCredentials({
        kubeconfig: this.form.kubeconfig || null,
      });
      this.saved = true;
      setTimeout(() => (this.saved = false), 3000);
    } catch {
      this.error = 'Failed to save credentials';
    } finally {
      this.saving = false;
    }
  }
}
