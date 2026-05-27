# Compact Tool Approval Card Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tall 3-section tool approval card with a compact single-row inline display showing the reconstructed command string and approve/deny buttons.

**Architecture:** The `ToolApproval` component gets a new `formattedCommand` computed getter that builds the full command string from `tool_input`, and the template is replaced with a single flex row — no separate header/body/footer.

**Tech Stack:** Angular 19, Bootstrap 5, TypeScript

---

## File Map

| File | Action |
|------|--------|
| `tool-call-ui/src/app/components/tool-approval/tool-approval.ts` | Update `formattedCommand` getter |
| `tool-call-ui/src/app/components/tool-approval/tool-approval.html` | Replace 3-section card with single flex row |
| `tool-call-ui/src/app/components/tool-approval/tool-approval.css` | Remove unused classes, add `.approval-command` |
| `tool-call-ui/src/app/components/tool-approval/tool-approval.spec.ts` | New — unit tests for `formattedCommand` |

---

### Task 1: Add unit tests for `formattedCommand`

**Files:**
- Create: `tool-call-ui/src/app/components/tool-approval/tool-approval.spec.ts`

- [ ] **Step 1: Create the spec file**

```typescript
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ToolApproval } from './tool-approval';

describe('ToolApproval', () => {
  let component: ToolApproval;
  let fixture: ComponentFixture<ToolApproval>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ToolApproval],
    }).compileComponents();
    fixture = TestBed.createComponent(ToolApproval);
    component = fixture.componentInstance;
  });

  it('should prepend "kubectl" for kubectl tool calls', () => {
    component.toolCall = {
      tool_use_id: 'id-1',
      tool_name: 'kubectl',
      tool_input: { args: 'get pods -n default' },
    };
    expect(component.formattedCommand).toBe('kubectl get pods -n default');
  });

  it('should fall back to "tool_name: first_value" for non-kubectl tools', () => {
    component.toolCall = {
      tool_use_id: 'id-2',
      tool_name: 'calculate',
      tool_input: { expression: '2+2' },
    };
    expect(component.formattedCommand).toBe('calculate: 2+2');
  });
});
```

- [ ] **Step 2: Run the tests and verify they fail**

```bash
cd tool-call-ui && npx ng test --include='**/tool-approval.spec.ts' --watch=false --browsers=ChromeHeadless
```

Expected: 2 failures — `formattedCommand` does not exist yet (currently returns JSON).

---

### Task 2: Update `formattedCommand` getter

**Files:**
- Modify: `tool-call-ui/src/app/components/tool-approval/tool-approval.ts`

- [ ] **Step 1: Replace the getter**

Current getter (lines 17–19):
```typescript
get formattedInput(): string {
  return JSON.stringify(this.toolCall.tool_input, null, 2);
}
```

Replace the entire class body with:
```typescript
export class ToolApproval {
  @Input() toolCall!: ToolCall;
  @Input() disabled = false;
  @Output() approved = new EventEmitter<boolean>();

  get formattedCommand(): string {
    if (this.toolCall.tool_name === 'kubectl') {
      return `kubectl ${this.toolCall.tool_input['args']}`;
    }
    const firstVal = Object.values(this.toolCall.tool_input)[0];
    return `${this.toolCall.tool_name}: ${firstVal}`;
  }

  approve(): void {
    this.approved.emit(true);
  }

  reject(): void {
    this.approved.emit(false);
  }
}
```

- [ ] **Step 2: Run the tests and verify they pass**

```bash
cd tool-call-ui && npx ng test --include='**/tool-approval.spec.ts' --watch=false --browsers=ChromeHeadless
```

Expected: 2 specs, 0 failures.

---

### Task 3: Update the template

**Files:**
- Modify: `tool-call-ui/src/app/components/tool-approval/tool-approval.html`

- [ ] **Step 1: Replace the entire template**

```html
<div class="card border-warning shadow-sm rounded-3 my-2">
  <div class="d-flex align-items-center px-3 py-2 gap-3">
    <span class="approval-icon">⚙️</span>
    <code class="flex-grow-1 font-monospace text-primary approval-command">{{ formattedCommand }}</code>
    <button class="btn btn-outline-danger btn-sm" [disabled]="disabled" (click)="reject()">✕ Deny</button>
    <button class="btn btn-outline-success btn-sm" [disabled]="disabled" (click)="approve()">✓ Allow</button>
  </div>
</div>
```

---

### Task 4: Update the CSS

**Files:**
- Modify: `tool-call-ui/src/app/components/tool-approval/tool-approval.css`

- [ ] **Step 1: Replace the entire file — remove unused classes, add `.approval-command`**

```css
.approval-icon {
  font-size: 1.1rem;
}

.approval-command {
  font-size: 0.87rem;
  word-break: break-all;
}
```

---

### Task 5: Build check and commit

- [ ] **Step 1: Run the full build to confirm no errors**

```bash
cd tool-call-ui && npx ng build --configuration=development 2>&1 | tail -20
```

Expected: `Build at: ... - Hash: ...` with no errors.

- [ ] **Step 2: Commit**

```bash
git add tool-call-ui/src/app/components/tool-approval/
git commit -m "feat(ui): compact tool-approval card — single inline row with full command"
```
