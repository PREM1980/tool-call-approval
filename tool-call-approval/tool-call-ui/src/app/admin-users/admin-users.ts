import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService, AppUser } from '../services/admin.service';

@Component({
  selector: 'app-admin-users',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-users.html',
  styleUrl: './admin-users.css',
})
export class AdminUsers implements OnInit {
  private adminService = inject(AdminService);

  users: AppUser[] = [];
  username = '';
  password = '';
  role: 'admin' | 'user' = 'user';
  loading = false;
  saving = false;
  error = '';
  success = '';

  async ngOnInit(): Promise<void> {
    await this.loadUsers();
  }

  async loadUsers(): Promise<void> {
    this.loading = true;
    this.error = '';
    try {
      this.users = await this.adminService.listUsers();
    } catch {
      this.error = 'Failed to load users';
    } finally {
      this.loading = false;
    }
  }

  async createUser(): Promise<void> {
    if (this.saving) return;
    this.error = '';
    this.success = '';
    this.saving = true;
    try {
      const user = await this.adminService.createUser(
        this.username.trim(),
        this.password,
        this.role,
      );
      this.users = [...this.users, user];
      this.username = '';
      this.password = '';
      this.role = 'user';
      this.success = `Created ${user.username}`;
    } catch {
      this.error = 'Could not create user';
    } finally {
      this.saving = false;
    }
  }
}
