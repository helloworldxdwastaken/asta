export interface Conversation {
  id: string;
  title: string;
  channel: string;
  approx_tokens?: number;
  last_active?: string;
  folder_id?: string | null;
}

export interface Folder {
  id: string;
  name: string;
  color?: string;
  count?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  provider?: string;
  activeTools: string[];
  completedTools: string[];
  imageUri?: string;
}

export interface Agent {
  id: string;
  name: string;
  icon?: string;
  description?: string;
  system_prompt?: string;
  model_override?: string;
  thinking_level?: string;
  category?: string;
  enabled?: boolean;
  skills?: string[];
}

export interface User {
  id: string;
  username: string;
  role: "admin" | "user";
}

export interface StreamChunk {
  type: "text" | "thinking" | "tool_start" | "tool_end" | "done" | "error" | "status" | "assistant_final";
  delta?: string;
  text?: string;
  name?: string;
  label?: string;
  conversation_id?: string;
  provider?: string;
  reply?: string;
  error?: string;
}
