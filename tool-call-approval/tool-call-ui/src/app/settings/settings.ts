import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './settings.html',
  styleUrl: './settings.css',
})
export class Settings {
  currentPassword = '';
  newPassword = '';
  confirmPassword = '';
  saving = false;
  success = '';
  error = '';

  constructor(public auth: AuthService) {}

  async savePassword(): Promise<void> {
    this.success = '';
    this.error = '';
    if (!this.currentPassword || !this.newPassword) {
      this.error = 'Enter your current password and a new password.';
      return;
    }
    if (this.newPassword !== this.confirmPassword) {
      this.error = 'The new passwords do not match.';
      return;
    }

    this.saving = true;
    try {
      await this.auth.changePassword(this.currentPassword, this.newPassword);
      this.currentPassword = '';
      this.newPassword = '';
      this.confirmPassword = '';
      this.success = 'Password updated.';
    } catch (error: unknown) {
      this.error = (error as { error?: { detail?: string } })?.error?.detail
        ?? 'Unable to update your password.';
    } finally {
      this.saving = false;
    }
  }
}
