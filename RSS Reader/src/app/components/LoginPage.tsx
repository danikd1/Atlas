import { useState, type FormEvent } from "react";
import { useNavigate, Link } from "react-router";
import { api } from "../lib/api";
import { authService } from "../lib/authService";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await api.login(email, password);
      authService.setToken(data.access_token);
      navigate("/", { replace: true });
    } catch (err: any) {
      setError(err.message || "Ошибка входа");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-center mb-6">Atlas RSS Reader</h1>
        <form
          onSubmit={handleSubmit}
          className="bg-white shadow rounded-lg p-6 space-y-4"
        >
          <h2 className="text-lg font-semibold text-gray-800">Вход</h2>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
              {error}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="user@example.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Пароль
            </label>
            <input
              type="password"
              required
              minLength={6}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Минимум 6 символов"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white rounded py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Вход..." : "Войти"}
          </button>

          <p className="text-sm text-center text-gray-500">
            Нет аккаунта?{" "}
            <Link to="/register" className="text-blue-600 hover:underline">
              Зарегистрироваться
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
