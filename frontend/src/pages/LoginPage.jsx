import React, { useState } from "react";
import { login } from "../lib/api";

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();

    const cleanUsername = username.trim().toLowerCase();
    const cleanPassword = password.trim();

    if (!cleanUsername || !cleanPassword) {
      setError("Please enter both username and password.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const session = await login(cleanUsername, cleanPassword);
      onLogin({ username: session.username, role: session.role });
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Invalid username or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="eyebrow">QuantumBlack Advisory Systems</div>
          <h2>Sign in to M&A Deal OS</h2>
          <p>Sign in with a role-based demo account below.</p>
        </div>

        <div className="login-hint">
          <span>Username (role)</span>
          <strong>analyst · associate · vp · director · md · admin</strong>
          <span>Password</span>
          <strong>your username + @100 (e.g. director@100)</strong>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <label>
            Username
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="e.g. director"
              autoComplete="username"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </label>

          {error && <div className="error-text">{error}</div>}

          <button type="submit" disabled={loading}>{loading ? "Signing in…" : "Sign In"}</button>
        </form>
      </div>
    </div>
  );
}
