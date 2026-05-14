export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
}

export interface ToolCall {
  tool_use_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface SseEvent {
  type:
    | 'thinking'
    | 'tool_call_pending'
    | 'tool_result'
    | 'tool_rejected'
    | 'message'
    | 'done'
    | 'error';
  content?: string;
  tool_use_id?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  result?: string;
}
