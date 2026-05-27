export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  reportUrl?: string;
  reportTitle?: string;
}

export interface ToolCall {
  tool_use_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface SessionSummary {
  session_id: string;
  created_at: number;
  updated_at: number | null;
  turn_count: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
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
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
}
