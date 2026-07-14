import { FormEvent, useState } from "react";
import { useAuth } from "./auth";

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={(event) => void submit(event)}>
        <h1>Учёт замечаний</h1>
        <p>Вход через учётную запись Active Directory</p>

        {error ? <div className="alert alert-error">{error}</div> : null}

        <div className="field">
          <label htmlFor="username">Логин</label>
          <input
            id="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            placeholder="sAMAccountName"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        <button className="btn btn-primary login-submit" type="submit" disabled={loading}>
          {loading ? "Вход..." : "Войти"}
        </button>
      </form>
    </div>
  );
}
