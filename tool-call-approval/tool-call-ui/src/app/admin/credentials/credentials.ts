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
    aws_access_key_id: '',
    aws_secret_access_key: '',
    aws_region: 'us-east-1',
    kubeconfig: '',
  };
  saving = false;
  saved = false;
  error = '';

  constructor(private adminService: AdminService) {}

  async ngOnInit() {
    const creds = await this.adminService.getCredentials();
    if (creds) {
      this.form.aws_access_key_id = creds.aws_access_key_id ?? '';
      this.form.aws_secret_access_key = creds.aws_secret_access_key ?? '';
      this.form.aws_region = creds.aws_region ?? 'us-east-1';
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
        aws_access_key_id: this.form.aws_access_key_id,
        aws_secret_access_key: this.form.aws_secret_access_key,
        aws_region: this.form.aws_region,
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
