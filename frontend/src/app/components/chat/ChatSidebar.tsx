import { Plus, MessageSquare, Trash2 } from "lucide-react";
import type { Conversation } from "../../lib/chatStorage";

function groupByDate(conversations: Conversation[]): { label: string; items: Conversation[] }[] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const todayItems: Conversation[] = [];
  const yesterdayItems: Conversation[] = [];
  const olderItems: Conversation[] = [];

  for (const c of conversations) {
    const d = new Date(c.updatedAt);
    d.setHours(0, 0, 0, 0);
    if (d >= today) todayItems.push(c);
    else if (d >= yesterday) yesterdayItems.push(c);
    else olderItems.push(c);
  }

  const groups = [];
  if (todayItems.length > 0) groups.push({ label: "Сегодня", items: todayItems });
  if (yesterdayItems.length > 0) groups.push({ label: "Вчера", items: yesterdayItems });
  if (olderItems.length > 0) groups.push({ label: "Раньше", items: olderItems });
  return groups;
}

interface ChatSidebarProps {
  conversations: Conversation[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

export function ChatSidebar({ conversations, currentId, onSelect, onNew, onDelete }: ChatSidebarProps) {
  const groups = groupByDate(conversations);

  return (
    <aside className="w-64 flex-shrink-0 border-r border-gray-200 bg-white flex flex-col h-full">
      <div className="p-3 border-b border-gray-100">
        <button
          onClick={onNew}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Новый чат
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {conversations.length === 0 ? (
          <p className="text-xs text-gray-400 text-center px-4 py-6">Диалогов пока нет</p>
        ) : (
          groups.map((group) => (
            <div key={group.label} className="mb-2">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider px-3 py-1.5">
                {group.label}
              </p>
              {group.items.map((conv) => (
                <div key={conv.id} className="group relative mx-1">
                  <button
                    onClick={() => onSelect(conv.id)}
                    className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-left text-sm transition-colors pr-8 ${
                      conv.id === currentId
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5 flex-shrink-0 text-gray-400" />
                    <span className="truncate">{conv.title}</span>
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(conv.id);
                    }}
                    className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-1 hover:bg-gray-200 rounded transition-all"
                    title="Удалить диалог"
                  >
                    <Trash2 className="w-3 h-3 text-gray-400" />
                  </button>
                </div>
              ))}
            </div>
          ))
        )}
      </div>
    </aside>
  );
}
