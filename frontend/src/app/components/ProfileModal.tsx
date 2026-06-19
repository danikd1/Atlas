import { useState, useEffect } from "react";
import { X, CheckCircle, XCircle, Loader2, Eye, EyeOff } from "lucide-react";
import { api } from "../lib/api";

const GIGACHAT_MODELS = ["GigaChat", "GigaChat-Pro", "GigaChat-Max"];

interface ProfileModalProps {
  onClose: () => void;
}

function getInitials(email: string): string {
  const name = email.split("@")[0];
  const parts = name.split(/[._-]/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function formatDate(iso?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function ProfileModal({ onClose }: ProfileModalProps) {
  // User info
  const [email, setEmail] = useState("");
  const [createdAt, setCreatedAt] = useState<string | undefined>();

  // GigaChat
  const [credentials, setCredentials] = useState("");
  const [model, setModel] = useState("GigaChat");
  const [hasSaved, setHasSaved] = useState(false);
  const [isEditingCreds, setIsEditingCreds] = useState(false);
  const [testStatus, setTestStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [testError, setTestError] = useState<string | null>(null);

  // Change password
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPw, setShowCurrentPw] = useState(false);
  const [showNewPw, setShowNewPw] = useState(false);
  const [pwStatus, setPwStatus] = useState<"idle" | "loading" | "ok" | "error">("idle");
  const [pwError, setPwError] = useState<string | null>(null);

  useEffect(() => {
    api.getMe().then((user) => {
      setEmail(user.email);
      setCreatedAt(user.created_at);
    }).catch(() => {});

    const savedCredentials = localStorage.getItem("gigachat_credentials");
    const savedModel = localStorage.getItem("gigachat_model");
    if (savedCredentials) {
      setHasSaved(true);
      // Не грузим значение в state сразу — показываем статический блок.
      // Значение загружается только когда пользователь явно нажимает «Изменить».
    }
    if (savedModel) setModel(savedModel);
  }, []);

  const handleTest = async () => {
    if (!credentials.trim()) return;
    setTestStatus("loading");
    setTestError(null);
    try {
      const result = await api.gigachatTest(credentials.trim(), model !== "GigaChat" ? model : undefined);
      if (result.ok) {
        setTestStatus("ok");
        // Автосохранение при успешной проверке
        localStorage.setItem("gigachat_credentials", credentials.trim());
        localStorage.setItem("gigachat_model", model);
        setHasSaved(true);
        setIsEditingCreds(false);
        setCredentials("");
      } else {
        setTestStatus("error");
        setTestError(result.error ?? "Неизвестная ошибка");
      }
    } catch (e: any) {
      setTestStatus("error");
      setTestError(e?.message ?? "Ошибка соединения");
    }
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      setPwStatus("error");
      setPwError("Пароли не совпадают");
      return;
    }
    if (newPassword.length < 6) {
      setPwStatus("error");
      setPwError("Минимум 6 символов");
      return;
    }
    setPwStatus("loading");
    setPwError(null);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPwStatus("ok");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
    } catch (e: any) {
      setPwStatus("error");
      setPwError(e?.message ?? "Ошибка смены пароля");
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-xl shadow-2xl w-full max-w-md relative overflow-y-auto max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-gray-100">
          <h2 className="text-lg font-semibold text-gray-900">Профиль</h2>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors">
            <X className="w-4 h-4 text-gray-500" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Avatar + account info */}
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
              <span className="text-white text-lg font-semibold">{email ? getInitials(email) : "?"}</span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{email || "—"}</p>
              <p className="text-xs text-gray-400 mt-0.5">Зарегистрирован {formatDate(createdAt)}</p>
            </div>
          </div>

          <hr className="border-gray-100" />

          {/* GigaChat section */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-4">GigaChat</h3>

            <div className="mb-4">
              <label className="block text-xs text-gray-500 mb-1.5">API-ключ</label>
              {hasSaved && !isEditingCreds ? (
                <div className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                  <span className="text-sm text-gray-500">●●●●●●●● (сохранено)</span>
                  <button
                    onClick={() => {
                      setIsEditingCreds(true);
                      setCredentials(localStorage.getItem("gigachat_credentials") ?? "");
                      setTestStatus("idle");
                    }}
                    className="text-xs text-blue-600 hover:underline ml-2 flex-shrink-0"
                  >
                    Изменить
                  </button>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <input
                    type="password"
                    value={credentials}
                    onChange={(e) => { setCredentials(e.target.value); setTestStatus("idle"); }}
                    placeholder="Вставьте ваш API-ключ"
                    autoFocus={isEditingCreds}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {hasSaved && isEditingCreds && (
                    <button
                      type="button"
                      onClick={() => { setIsEditingCreds(false); setCredentials(""); setTestStatus("idle"); }}
                      className="text-xs text-gray-400 hover:text-gray-600"
                    >
                      Отмена
                    </button>
                  )}
                </div>
              )}
            </div>

            <div className="mb-4">
              <label className="block text-xs text-gray-500 mb-1.5">Модель</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              >
                {GIGACHAT_MODELS.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            {testStatus === "error" && (
              <div className="flex items-start gap-2 text-sm text-red-600 mb-3">
                <XCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{testError ?? "Ошибка подключения"}</span>
              </div>
            )}

            <div className="flex items-center gap-3">
              <button
                onClick={handleTest}
                disabled={!credentials.trim() || testStatus === "loading"}
                className="flex items-center gap-1.5 px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {testStatus === "loading" && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {testStatus !== "loading" && testStatus === "ok" && <CheckCircle className="w-3.5 h-3.5 text-green-500" />}
                Проверить подключение
              </button>
              {testStatus === "ok" && (
                <span className="text-xs text-gray-400">сохранено</span>
              )}
            </div>
          </div>

          <hr className="border-gray-100" />

          {/* Change password */}
          <div>
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Смена пароля</h3>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1.5">Текущий пароль</label>
                <div className="relative">
                  <input
                    type={showCurrentPw ? "text" : "password"}
                    value={currentPassword}
                    onChange={(e) => { setCurrentPassword(e.target.value); setPwStatus("idle"); }}
                    placeholder="Введите текущий пароль"
                    className="w-full px-3 py-2 pr-9 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPw(!showCurrentPw)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showCurrentPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1.5">Новый пароль</label>
                <div className="relative">
                  <input
                    type={showNewPw ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => { setNewPassword(e.target.value); setPwStatus("idle"); }}
                    placeholder="Минимум 6 символов"
                    className="w-full px-3 py-2 pr-9 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPw(!showNewPw)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showNewPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1.5">Подтверждение пароля</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => { setConfirmPassword(e.target.value); setPwStatus("idle"); }}
                  placeholder="Повторите новый пароль"
                  className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            {pwStatus === "ok" && (
              <div className="flex items-center gap-2 text-sm text-green-600 mt-3">
                <CheckCircle className="w-4 h-4" /> Пароль изменён
              </div>
            )}
            {pwStatus === "error" && (
              <div className="flex items-start gap-2 text-sm text-red-600 mt-3">
                <XCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{pwError}</span>
              </div>
            )}

            <button
              onClick={handleChangePassword}
              disabled={!currentPassword || !newPassword || !confirmPassword || pwStatus === "loading"}
              className="mt-4 w-full flex items-center justify-center gap-1.5 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {pwStatus === "loading" && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              Сменить пароль
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
