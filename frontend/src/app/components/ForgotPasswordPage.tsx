import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router";
import { api } from "../lib/api";

type Step = "email" | "code" | "newPassword" | "done";

export function ForgotPasswordPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSendCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.forgotPassword(email);
      setStep("code");
    } catch (err: any) {
      setError(err.message || "Ошибка отправки кода");
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyCode(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.verifyResetCode(email, code);
      setStep("newPassword");
    } catch (err: any) {
      setError(err.message || "Неверный код");
    } finally {
      setLoading(false);
    }
  }

  async function handleResetPassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirmPassword) {
      setError("Пароли не совпадают");
      return;
    }
    setLoading(true);
    try {
      await api.resetPassword(email, code, newPassword);
      setStep("done");
    } catch (err: any) {
      setError(err.message || "Ошибка сброса пароля");
    } finally {
      setLoading(false);
    }
  }

  const cardStyle = {
    background: "rgba(255,255,255,0.05)",
    backdropFilter: "blur(20px)",
    border: "1px solid rgba(255,255,255,0.1)",
    boxShadow: "0 25px 50px rgba(0,0,0,0.4)",
  };

  const inputStyle = {
    background: "rgba(255,255,255,0.07)",
    border: "1px solid rgba(255,255,255,0.12)",
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden bg-[#0f172a]">
      <div
        className="absolute inset-0 opacity-[0.15]"
        style={{
          backgroundImage: "radial-gradient(circle, #94a3b8 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-br from-blue-900/40 via-transparent to-indigo-900/40" />

      <div className="relative z-10 w-full max-w-sm mx-4">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-black tracking-widest uppercase text-white" style={{ letterSpacing: "0.2em" }}>
            Atlas
          </h1>
          <p className="text-slate-400 text-sm mt-3">Восстановление пароля</p>
        </div>

        <div className="rounded-2xl p-7 space-y-4" style={cardStyle}>

          {/* Шаг 1 — ввод email */}
          {step === "email" && (
            <form onSubmit={handleSendCode} className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-2">Забыли пароль?</h2>
              <p className="text-sm text-slate-400">Введите ваш email — мы отправим код подтверждения.</p>

              {error && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  style={inputStyle}
                  placeholder="user@example.com"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg py-2.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors disabled:opacity-50 mt-2"
              >
                {loading ? "Отправка..." : "Отправить код"}
              </button>

              <p className="text-sm text-center text-slate-400 pt-1">
                <Link to="/login" className="text-blue-400 hover:text-blue-300 hover:underline">
                  Вернуться ко входу
                </Link>
              </p>
            </form>
          )}

          {/* Шаг 2 — ввод кода */}
          {step === "code" && (
            <form onSubmit={handleVerifyCode} className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-2">Введите код</h2>
              <p className="text-sm text-slate-400">
                Мы отправили 6-значный код на <span className="text-white">{email}</span>. Проверьте папку «Входящие» и «Спам».
              </p>

              {error && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Код из письма</label>
                <input
                  type="text"
                  required
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  className="w-full rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-center tracking-[0.5em] text-lg font-mono"
                  style={inputStyle}
                  placeholder="000000"
                />
              </div>

              <button
                type="submit"
                disabled={loading || code.length !== 6}
                className="w-full rounded-lg py-2.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors disabled:opacity-50 mt-2"
              >
                {loading ? "Проверка..." : "Подтвердить"}
              </button>

              <p className="text-sm text-center text-slate-400 pt-1">
                <button type="button" onClick={() => setStep("email")} className="text-blue-400 hover:text-blue-300 hover:underline">
                  Изменить email
                </button>
              </p>
            </form>
          )}

          {/* Шаг 3 — новый пароль */}
          {step === "newPassword" && (
            <form onSubmit={handleResetPassword} className="space-y-4">
              <h2 className="text-lg font-semibold text-white mb-2">Новый пароль</h2>

              {error && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Новый пароль</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  style={inputStyle}
                  placeholder="Минимум 8 символов"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Повторите пароль</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full rounded-lg px-3 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  style={inputStyle}
                  placeholder="Повторите пароль"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-lg py-2.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors disabled:opacity-50 mt-2"
              >
                {loading ? "Сохранение..." : "Сохранить пароль"}
              </button>
            </form>
          )}

          {/* Шаг 4 — готово */}
          {step === "done" && (
            <div className="space-y-4 text-center">
              <div className="flex items-center justify-center">
                <div className="w-16 h-16 rounded-full bg-slate-700/60 flex items-center justify-center">
                  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                    <path d="M7 16.5L13 22.5L25 10" stroke="#22c55e" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </div>
              </div>
              <h2 className="text-lg font-semibold text-white">Пароль изменён</h2>
              <p className="text-sm text-slate-400">Теперь вы можете войти с новым паролем.</p>
              <button
                onClick={() => navigate("/login")}
                className="w-full rounded-lg py-2.5 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 transition-colors mt-2"
              >
                Войти
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
