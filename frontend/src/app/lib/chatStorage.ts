const STORAGE_KEY = "atlas_chat_conversations";
const MAX_CONVERSATIONS = 50;

export interface ChatSource {
  title: string;
  link: string;
  published_at: string;
  snippet?: string;
  article_id?: number;
}

export interface ChatDisplayMessage {
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
}

// Raw message format for the API (includes function/tool messages)
export type ApiMessage = Record<string, unknown>;

export interface Conversation {
  id: string;
  title: string;
  displayMessages: ChatDisplayMessage[];
  apiMessages: ApiMessage[];
  createdAt: string;
  updatedAt: string;
}

function load(): Conversation[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function persist(convs: Conversation[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(convs.slice(0, MAX_CONVERSATIONS)));
}

export function getConversations(): Conversation[] {
  return load();
}

export function getConversation(id: string): Conversation | null {
  return load().find((c) => c.id === id) ?? null;
}

export function saveConversation(conv: Conversation): void {
  const others = load().filter((c) => c.id !== conv.id);
  persist([conv, ...others]);
}

export function deleteConversation(id: string): void {
  persist(load().filter((c) => c.id !== id));
}

export function createConversation(firstMessage: string): Conversation {
  return {
    id: crypto.randomUUID(),
    title: firstMessage.slice(0, 50),
    displayMessages: [],
    apiMessages: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}
