import { useState, useCallback } from "react";
import { ChatSidebar } from "./chat/ChatSidebar";
import { ChatMessages } from "./chat/ChatMessages";
import { ChatInput } from "./chat/ChatInput";
import { ArticleSlidePanel } from "./chat/ArticleSlidePanel";
import { api } from "../lib/api";
import {
  getConversations,
  getConversation,
  saveConversation,
  deleteConversation,
  createConversation,
  type Conversation,
} from "../lib/chatStorage";

function getInitialState(): { conversations: Conversation[]; currentId: string | null } {
  const conversations = getConversations();
  return { conversations, currentId: conversations[0]?.id ?? null };
}

export function ChatPage() {
  const [{ conversations, currentId }, setPageState] = useState(getInitialState);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openArticleId, setOpenArticleId] = useState<number | null>(null);

  const currentConv = currentId ? (conversations.find((c) => c.id === currentId) ?? null) : null;

  const refreshConversations = useCallback((nextCurrentId?: string | null) => {
    setPageState((prev) => ({
      conversations: getConversations(),
      currentId: nextCurrentId !== undefined ? nextCurrentId : prev.currentId,
    }));
  }, []);

  const handleNew = useCallback(() => {
    setPageState((prev) => ({ ...prev, currentId: null }));
    setError(null);
  }, []);

  const handleSelect = useCallback((id: string) => {
    setPageState((prev) => ({ ...prev, currentId: id }));
    setError(null);
  }, []);

  const handleDelete = useCallback((id: string) => {
    deleteConversation(id);
    setPageState((prev) => ({
      conversations: getConversations(),
      currentId: prev.currentId === id ? null : prev.currentId,
    }));
  }, []);

  const handleSend = useCallback(
    async (message: string) => {
      setError(null);
      setIsLoading(true);

      const isNewConv = !currentId;
      let conv: Conversation;

      if (currentId) {
        conv = getConversation(currentId) ?? createConversation(message);
      } else {
        conv = createConversation(message);
      }

      // Optimistically add user message and switch to this conversation
      const withUserMsg: Conversation = {
        ...conv,
        displayMessages: [...conv.displayMessages, { role: "user" as const, content: message }],
        updatedAt: new Date().toISOString(),
      };
      saveConversation(withUserMsg);
      refreshConversations(conv.id);

      try {
        const result = await api.sendChatMessage(message, conv.apiMessages);

        const finalConv: Conversation = {
          ...withUserMsg,
          displayMessages: [
            ...withUserMsg.displayMessages,
            { role: "assistant" as const, content: result.answer, sources: result.sources },
          ],
          apiMessages: result.messages,
          updatedAt: new Date().toISOString(),
        };
        saveConversation(finalConv);
        refreshConversations(conv.id);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Что-то пошло не так. Попробуйте снова.");

        if (isNewConv) {
          // New conversation never had a successful response — delete it entirely
          deleteConversation(conv.id);
          refreshConversations(null);
        } else {
          // Existing conversation — roll back to state before this message
          saveConversation(conv);
          refreshConversations(conv.id);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [currentId, refreshConversations]
  );

  const handleExampleClick = useCallback(
    (question: string) => handleSend(question),
    [handleSend]
  );

  return (
    <div className="h-full flex overflow-hidden bg-gray-50">
      <ChatSidebar
        conversations={conversations}
        currentId={currentId}
        onSelect={handleSelect}
        onNew={handleNew}
        onDelete={handleDelete}
      />

      <div className="flex flex-col flex-1 overflow-hidden bg-white">
        {error && (
          <div className="mx-4 mt-3 px-4 py-2.5 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex-shrink-0">
            {error}
          </div>
        )}

        <ChatMessages
          messages={currentConv?.displayMessages ?? []}
          isLoading={isLoading}
          onExampleClick={handleExampleClick}
          onOpenArticle={setOpenArticleId}
        />

        <ChatInput onSend={handleSend} isLoading={isLoading} />
      </div>

      {openArticleId !== null && (
        <ArticleSlidePanel
          articleId={openArticleId}
          onClose={() => setOpenArticleId(null)}
        />
      )}
    </div>
  );
}
