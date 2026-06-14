import { Component, OnInit, inject, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ChatMessage, SessionSummary } from '../../models/types';
import { SessionsService } from '../../services/sessions.service';

export type SessionMessageBlock =
  | { type: 'paragraph'; text: string }
  | { type: 'heading'; level: 1 | 2 | 3 | 4; text: string }
  | { type: 'list'; items: string[] }
  | { type: 'table'; headers: string[]; rows: string[][] }
  | { type: 'code'; text: string }
  | { type: 'rule' };

export interface FormattedChatMessage extends ChatMessage {
  blocks: SessionMessageBlock[];
}

@Component({
  selector: 'app-sessions',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './sessions.html',
  styleUrl: './sessions.css',
})
export class Sessions implements OnInit {
  private sessionsService = inject(SessionsService);

  @Output() openChat = new EventEmitter<string>();

  sessions: SessionSummary[] = [];
  selectedId: string | null = null;
  history: FormattedChatMessage[] = [];
  loadingSessions = false;
  loadingHistory = false;
  error = '';
  historyError = '';

  async ngOnInit(): Promise<void> {
    this.loadingSessions = true;
    try {
      this.sessions = await this.sessionsService.getAll();
    } catch {
      this.error = 'Failed to load sessions';
    } finally {
      this.loadingSessions = false;
    }
  }

  async selectSession(id: string): Promise<void> {
    if (this.selectedId === id) {
      this.selectedId = null;
      this.history = [];
      return;
    }
    this.selectedId = id;
    this.history = [];
    this.historyError = '';
    this.loadingHistory = true;
    try {
      const messages = await this.sessionsService.getHistory(id);
      this.history = messages.map(formatChatMessage);
    } catch {
      this.historyError = 'Failed to load chat history';
    } finally {
      this.loadingHistory = false;
    }
  }

  formatTimestamp(epoch: number): string {
    return new Date(epoch * 1000).toLocaleString();
  }

  shortId(id: string): string {
    return id.slice(0, 8);
  }
}

export function formatChatMessage(message: ChatMessage): FormattedChatMessage {
  return {
    ...message,
    blocks: formatSessionContent(message.content),
  };
}

export function formatSessionContent(content: string): SessionMessageBlock[] {
  const lines = normalizeMarkdown(content).split('\n');
  const blocks: SessionMessageBlock[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index] ?? '';
    const trimmed = line.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith('```')) {
      const parsedCode = parseCodeBlock(lines, index);
      blocks.push(parsedCode.block);
      index = parsedCode.nextIndex;
      continue;
    }

    const table = parseTable(lines, index);
    if (table) {
      blocks.push(table.block);
      index = table.nextIndex;
      continue;
    }

    const heading = trimmed.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      blocks.push({
        type: 'heading',
        level: heading[1].length as 1 | 2 | 3 | 4,
        text: cleanInline(heading[2]),
      });
      index += 1;
      continue;
    }

    if (/^(?:-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
      blocks.push({ type: 'rule' });
      index += 1;
      continue;
    }

    const list = parseList(lines, index);
    if (list) {
      blocks.push(list.block);
      index = list.nextIndex;
      continue;
    }

    const paragraphLines = [trimmed];
    index += 1;

    while (index < lines.length && !isBlockStart(lines, index)) {
      paragraphLines.push(lines[index].trim());
      index += 1;
    }

    blocks.push({
      type: 'paragraph',
      text: cleanInline(paragraphLines.join(' ')),
    });
  }

  return blocks.length > 0 ? blocks : [{ type: 'paragraph', text: '' }];
}

function normalizeMarkdown(content: string): string {
  return content
    .replace(/\r\n?/g, '\n')
    .replace(/([^\n])(?=#{1,4}\s)/g, '$1\n');
}

function parseCodeBlock(
  lines: string[],
  startIndex: number
): { block: SessionMessageBlock; nextIndex: number } {
  const codeLines: string[] = [];
  let index = startIndex + 1;

  while (index < lines.length) {
    const line = lines[index] ?? '';
    if (line.trim().startsWith('```')) {
      return {
        block: { type: 'code', text: codeLines.join('\n') },
        nextIndex: index + 1,
      };
    }
    codeLines.push(line);
    index += 1;
  }

  return {
    block: { type: 'code', text: codeLines.join('\n') },
    nextIndex: index,
  };
}

function parseTable(
  lines: string[],
  startIndex: number
): { block: SessionMessageBlock; nextIndex: number } | null {
  const headerLine = lines[startIndex]?.trim() ?? '';
  const dividerLine = lines[startIndex + 1]?.trim() ?? '';

  if (!looksLikeTableRow(headerLine) || !isTableDivider(dividerLine)) {
    return null;
  }

  const headers = splitTableCells(headerLine).map(cleanInline);
  const rows: string[][] = [];
  let index = startIndex + 2;

  while (index < lines.length && looksLikeTableRow(lines[index] ?? '')) {
    const cells = splitTableCells(lines[index] ?? '').map(cleanInline);
    rows.push(normalizeTableRow(cells, headers.length));
    index += 1;
  }

  return {
    block: { type: 'table', headers, rows },
    nextIndex: index,
  };
}

function parseList(
  lines: string[],
  startIndex: number
): { block: SessionMessageBlock; nextIndex: number } | null {
  const items: string[] = [];
  let index = startIndex;

  while (index < lines.length) {
    const match = (lines[index] ?? '').trim().match(/^(?:[-*]|\d+\.)\s+(.+)$/);
    if (!match) break;
    items.push(cleanInline(match[1]));
    index += 1;
  }

  return items.length > 0 ? { block: { type: 'list', items }, nextIndex: index } : null;
}

function isBlockStart(lines: string[], index: number): boolean {
  const trimmed = (lines[index] ?? '').trim();
  return (
    !trimmed ||
    trimmed.startsWith('```') ||
    /^(#{1,4})\s+/.test(trimmed) ||
    /^(?:-{3,}|\*{3,}|_{3,})$/.test(trimmed) ||
    /^(?:[-*]|\d+\.)\s+/.test(trimmed) ||
    parseTable(lines, index) !== null
  );
}

function looksLikeTableRow(line: string): boolean {
  return line.includes('|') && splitTableCells(line).length > 1;
}

function isTableDivider(line: string): boolean {
  const cells = splitTableCells(line);
  return cells.length > 1 && cells.every(cell => /^:?-{3,}:?$/.test(cell.trim()));
}

function splitTableCells(line: string): string[] {
  let trimmed = line.trim();
  if (trimmed.startsWith('|')) trimmed = trimmed.slice(1);
  if (trimmed.endsWith('|')) trimmed = trimmed.slice(0, -1);
  return trimmed.split('|').map(cell => cell.trim());
}

function normalizeTableRow(cells: string[], expectedLength: number): string[] {
  if (cells.length === expectedLength) return cells;
  if (cells.length > expectedLength) return cells.slice(0, expectedLength);
  return [...cells, ...Array.from({ length: expectedLength - cells.length }, () => '')];
}

function cleanInline(value: string): string {
  return value
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .trim();
}
