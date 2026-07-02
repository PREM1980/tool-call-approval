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
  roleDrafts: Record<string, 'admin' | 'user'> = {};
  loading = false;
  saving = false;
  savingRoleIds = new Set<string>();
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
      this.syncRoleDrafts(this.users);
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
      this.roleDrafts = { ...this.roleDrafts, [user.id]: user.role };
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

  roleChanged(user: AppUser): boolean {
    return (this.roleDrafts[user.id] ?? user.role) !== user.role;
  }

  isSavingRole(userId: string): boolean {
    return this.savingRoleIds.has(userId);
  }

  async updateUserRole(user: AppUser): Promise<void> {
    if (this.isSavingRole(user.id)) return;

    const nextRole = this.roleDrafts[user.id] ?? user.role;
    if (nextRole === user.role) return;

    this.error = '';
    this.success = '';
    this.savingRoleIds = new Set([...this.savingRoleIds, user.id]);
    try {
      const updated = await this.adminService.updateUserRole(user.id, nextRole);
      this.users = this.users.map((existing) =>
        existing.id === updated.id ? updated : existing,
      );
      this.roleDrafts = { ...this.roleDrafts, [updated.id]: updated.role };
      this.success = `Updated ${updated.username}`;
    } catch {
      this.error = 'Could not update user';
    } finally {
      const savingRoleIds = new Set(this.savingRoleIds);
      savingRoleIds.delete(user.id);
      this.savingRoleIds = savingRoleIds;
    }
  }

  private syncRoleDrafts(users: AppUser[]): void {
    this.roleDrafts = users.reduce<Record<string, 'admin' | 'user'>>((drafts, user) => {
      drafts[user.id] = user.role;
      return drafts;
    }, {});
  }
}
