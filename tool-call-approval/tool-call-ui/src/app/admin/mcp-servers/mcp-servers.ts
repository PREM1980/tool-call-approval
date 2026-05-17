import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AdminService } from '../../services/admin.service';

interface SlotForm {
  name: string;
  config: string;
  saving: boolean;
  saved: boolean;
  error: string;
}

@Component({
  selector: 'app-mcp-servers',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './mcp-servers.html',
  styleUrl: './mcp-servers.css',
})
export class McpServers implements OnInit {
  slots: SlotForm[] = Array.from({ length: 5 }, () => ({
    name: '',
    config: '',
    saving: false,
    saved: false,
    error: '',
  }));

  constructor(private adminService: AdminService) {}

  async ngOnInit() {
    const servers = await this.adminService.getMcpServers();
    for (const server of servers) {
      const slot = this.slots[server.position - 1];
      slot.name = server.name;
      slot.config = JSON.stringify(server.config, null, 2);
    }
  }

  async save(idx: number) {
    const slot = this.slots[idx];
    slot.error = '';
    let config: Record<string, unknown>;
    try {
      config = JSON.parse(slot.config || '{}');
    } catch {
      slot.error = 'Invalid JSON';
      return;
    }
    slot.saving = true;
    try {
      await this.adminService.saveMcpServer(idx + 1, slot.name, config);
      slot.saved = true;
      setTimeout(() => (slot.saved = false), 3000);
    } catch {
      slot.error = 'Failed to save';
    } finally {
      slot.saving = false;
    }
  }

  async clear(idx: number) {
    try {
      await this.adminService.deleteMcpServer(idx + 1);
    } catch {
      // slot may not exist yet — ignore
    }
    Object.assign(this.slots[idx], { name: '', config: '', error: '' });
  }
}
