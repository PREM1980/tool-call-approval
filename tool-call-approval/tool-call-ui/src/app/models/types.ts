export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  data?: MessageData;
  user?: string | Record<string, unknown> | null;
  agent?: string | Record<string, unknown> | null;
  platform_context?: PlatformContext | null;
  ambient_context?: AmbientContext | null;
  reportUrl?: string;
  reportTitle?: string;
  trace_run_id?: string | null;
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
  first_message?: string | null;
  system_prompt_id?: string | null;
  system_prompt_name?: string | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  data?: MessageData;
  timestamp?: string | null;
  user?: string | Record<string, unknown> | null;
  agent?: string | Record<string, unknown> | null;
  platform_context?: PlatformContext | null;
  ambient_context?: AmbientContext | null;
}

export interface SseEvent {
  type:
    | 'run_started'
    | 'run_completed'
    | 'run_failed'
    | 'model_request'
    | 'model_response'
    | 'message_delta'
    | 'tool_started'
    | 'tool_failed'
    | 'approval_received'
    | 'approval_timed_out'
    | 'thinking'
    | 'tool_call_pending'
    | 'tool_result'
    | 'tool_rejected'
    | 'message'
    | 'done'
    | 'error'
    | 'stream_error';
  content?: string;
  tool_use_id?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  result?: string;
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
  sequence?: number;
  run_id?: string | null;
  occurred_at?: string;
}

export interface DebugEvent {
  sequence?: number;
  run_id?: string | null;
  event_type: string;
  payload: Record<string, unknown>;
  occurred_at: string;
}

export interface FileObject {
  file_path: string;
  file_content: string;
  refers_persistent_file?: string | null;
}

export interface Command {
  command: string;
  execute?: boolean;
  rejection_reason?: string | null;
  files?: FileObject[] | null;
}

export interface ExecutedCommand {
  command: string;
  output: string;
}

export interface UrlConfig {
  url: string;
  description: string;
}

export interface PlatformContext {
  k8s_namespace?: string | null;
  duplo_base_url?: string | null;
  duplo_token?: string | null;
  tenant_name?: string | null;
  kubeconfig?: string | null;
}

export interface AmbientContext {
  user_terminal_cmds: ExecutedCommand[];
}

export interface MessageData {
  cmds: Command[];
  executed_cmds: ExecutedCommand[];
  url_configs: UrlConfig[];
  user_file_uploads: FileObject[];
}

export interface ApiMessage {
  role: 'user' | 'assistant';
  content?: string;
  data?: MessageData;
  timestamp?: string | null;
  user?: string | Record<string, unknown> | null;
  agent?: string | Record<string, unknown> | null;
  platform_context?: PlatformContext | null;
  ambient_context?: AmbientContext | null;
}

export interface SessionContext {
  session_id?: string | null;
  instance_id?: string | null;
  persona_id?: string | null;
  persona_ids?: string[];
  system_prompt_id?: string | null;
  model_id?: string | null;
  provider?: string | null;
}

export interface ApprovalContext {
  approved: boolean;
  tool_use_id?: string | null;
  tool_input?: Record<string, unknown> | null;
}

export interface ApprovalDecision {
  approved: boolean;
  tool_input: Record<string, unknown>;
}

export interface MessageEnvelope {
  session: SessionContext;
  messages: ApiMessage[];
  approval: ApprovalContext | null;
}
