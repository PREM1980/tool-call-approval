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

  it('should emit edited parameters when approved', () => {
    component.toolCall = {
      tool_use_id: 'id-3',
      tool_name: 'get_weather',
      tool_input: { city: 'London' },
    };
    component.ngOnChanges({
      toolCall: { currentValue: component.toolCall, previousValue: null, firstChange: true, isFirstChange: () => true },
    });
    component.editableInput['city'] = 'Boston';
    let decision: unknown;
    component.approved.subscribe(value => decision = value);

    component.approve();

    expect(decision).toEqual({ approved: true, tool_input: { city: 'Boston' } });
  });
});
