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
