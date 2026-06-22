import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.html',
  styleUrl: './login.css',
})
export class Login {
  private auth = inject(AuthService);
  private router = inject(Router);

  username = 'admin';
  password = '';
  loading = false;
  error = '';

  async submit(): Promise<void> {
    if (this.loading) return;
    this.error = '';
    this.loading = true;
    try {
      await this.auth.login(this.username.trim(), this.password);
      await this.router.navigateByUrl('/ai-engg');
    } catch {
      this.error = 'Invalid username or password';
    } finally {
      this.loading = false;
    }
  }
}
