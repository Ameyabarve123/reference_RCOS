export type Person = {
  uid: string;
  first_name: string;
  last_name: string;
  email: string;
  phone_number: string | null;
  is_admin: boolean;
};

export type SessionTokens = {
  access_token: string;
  refresh_token: string;
  expires_at?: number | null;
};

export type AuthResponse = {
  person: Person | null;
  confirmation_required: boolean;
  session?: SessionTokens;
};

export type Folder = {
  id: string;
  name: string;
  timestamp: string;
};

export type LibraryItem = {
  id: string;
  kind: "file" | "text";
  name: string;
  folder_id: string;
  timestamp: string;
  chunk_count: number;
};

export type Library = {
  folders: Folder[];
  items: LibraryItem[];
};

export type IngestResult = {
  id: string;
  kind: "file" | "text";
  document_kind: string;
  name: string;
  folder_id: string;
  strategy: string;
  chunk_count: number;
  truncated: boolean;
  steps: string[];
};

export type Citation = {
  chunk_id: string;
  excerpt: string;
  source: string;
  similarity?: number | null;
};

export type ChatMessage = {
  message_id: string;
  role: "user" | "assistant";
  message: string;
  timestamp: string;
  query_mode?: string | null;
  citations?: Citation[];
};

export type ChatSummary = {
  id: string;
  chat_name: string;
  timestamp: string;
};

export type ChatDetail = ChatSummary & {
  messages: ChatMessage[];
};

export type AnswerResult = {
  mode: string;
  router_reason: string;
  steps: string[];
  assistant_message: ChatMessage;
};
