import {
  AmbientContext,
  ApiMessage,
  ApprovalContext,
  MessageData,
  MessageEnvelope,
  PlatformContext,
  SessionContext,
} from '../models/types';

export function emptySessionContext(): SessionContext {
  return {
    session_id: null,
    instance_id: null,
    persona_id: null,
    persona_ids: [],
    system_prompt_id: null,
    model_id: null,
    provider: null,
  };
}

export function emptyMessageData(): MessageData {
  return {
    cmds: [],
    executed_cmds: [],
    url_configs: [],
    user_file_uploads: [],
  };
}

export function emptyPlatformContext(): PlatformContext {
  return {
    k8s_namespace: null,
    duplo_base_url: null,
    duplo_token: null,
    tenant_name: null,
    aws_credentials: null,
    kubeconfig: null,
  };
}

export function emptyAmbientContext(): AmbientContext {
  return { user_terminal_cmds: [] };
}

export function normalizeSessionContext(session: SessionContext = {}): SessionContext {
  return {
    ...emptySessionContext(),
    ...session,
    persona_ids: [...(session.persona_ids ?? [])],
  };
}

export function normalizeMessageData(data?: MessageData | null): MessageData {
  return {
    cmds: (data?.cmds ?? []).map(command => ({ ...command })),
    executed_cmds: (data?.executed_cmds ?? []).map(command => ({ ...command })),
    url_configs: (data?.url_configs ?? []).map(config => ({ ...config })),
    user_file_uploads: (data?.user_file_uploads ?? []).map(file => ({ ...file })),
  };
}

export function normalizePlatformContext(context?: PlatformContext | null): PlatformContext {
  return {
    ...emptyPlatformContext(),
    ...(context ?? {}),
  };
}

export function normalizeAmbientContext(context?: AmbientContext | null): AmbientContext {
  return {
    user_terminal_cmds: (context?.user_terminal_cmds ?? []).map(command => ({ ...command })),
  };
}

export function normalizeApiMessage(message: ApiMessage): ApiMessage {
  const normalized: ApiMessage = {
    role: message.role,
    content: message.content ?? '',
    data: normalizeMessageData(message.data),
    timestamp: message.timestamp ?? new Date().toISOString(),
    user: message.user ?? null,
    agent: message.agent ?? null,
  };

  if (message.role === 'user') {
    normalized.platform_context = normalizePlatformContext(message.platform_context);
    normalized.ambient_context = normalizeAmbientContext(message.ambient_context);
  }

  return normalized;
}

export function normalizeApproval(
  approval?: ApprovalContext | null,
): ApprovalContext | null {
  if (!approval) return null;
  return {
    approved: approval.approved,
    tool_use_id: approval.tool_use_id ?? null,
  };
}

export function createMessageEnvelope(
  session: SessionContext,
  messages: ApiMessage[] = [],
  approval?: ApprovalContext | null,
): MessageEnvelope {
  return {
    session: normalizeSessionContext(session),
    messages: messages.map(normalizeApiMessage),
    approval: normalizeApproval(approval),
  };
}
