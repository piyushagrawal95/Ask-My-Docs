import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabaseClient";

export default function AuthPage() {
  const [mode, setMode] = useState("signin"); // "signin" | "signup"
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);

    if (mode === "signin") {
      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      setBusy(false);
      if (signInError) {
        setError(signInError.message);
        return;
      }
      navigate("/");
    } else {
      const { data: signUpData, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: { full_name: fullName },
          // After the user clicks the confirmation link, Supabase redirects
          // here — back to this same sign-in/sign-up page — instead of
          // straight into the app.
          emailRedirectTo: `${window.location.origin}/auth`,
        },
      });
      setBusy(false);
      if (signUpError) {
        setError(signUpError.message);
        return;
      }

      // Supabase returns a "successful" response even when the email is already
      // registered (email enumeration protection) — the tell is an empty
      // `identities` array on the returned user. Detect that case explicitly.
      const alreadyRegistered = signUpData?.user?.identities?.length === 0;
      if (alreadyRegistered) {
        setError("An account with this email already exists. Please sign in instead.");
        setMode("signin");
        return;
      }

      setInfo("Check your email to confirm your account, then sign in.");
      setMode("signin");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-10 text-center">
          <p className="font-serif text-3xl text-ink">Ask My Docs</p>
          <p className="mt-2 text-sm text-ink-soft">
            Read your documents by asking them questions.
          </p>
        </div>

        <div className="border border-stone-line bg-stone-card p-8">
          <div className="mb-6 flex gap-6 border-b border-stone-line text-sm">
            <button
              className={`pb-3 -mb-px border-b-2 transition-colors ${
                mode === "signin"
                  ? "border-brass text-ink font-medium"
                  : "border-transparent text-ink-soft"
              }`}
              onClick={() => setMode("signin")}
              type="button"
            >
              Sign in
            </button>
            <button
              className={`pb-3 -mb-px border-b-2 transition-colors ${
                mode === "signup"
                  ? "border-brass text-ink font-medium"
                  : "border-transparent text-ink-soft"
              }`}
              onClick={() => setMode("signup")}
              type="button"
            >
              Create account
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "signup" && (
              <div>
                <label className="block text-xs text-ink-soft mb-1.5" htmlFor="fullName">
                  Full name
                </label>
                <input
                  id="fullName"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full border border-stone-line bg-white/60 px-3 py-2 text-sm text-ink focus:border-brass outline-none"
                  placeholder="Jane Doe"
                />
              </div>
            )}
            <div>
              <label className="block text-xs text-ink-soft mb-1.5" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-stone-line bg-white/60 px-3 py-2 text-sm text-ink focus:border-brass outline-none"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-xs text-ink-soft mb-1.5" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                minLength={6}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-stone-line bg-white/60 px-3 py-2 text-sm text-ink focus:border-brass outline-none"
                placeholder="••••••••"
              />
            </div>

            {error && <p className="text-sm text-rust">{error}</p>}
            {info && <p className="text-sm text-sage">{info}</p>}

            <button
              type="submit"
              disabled={busy}
              className="w-full bg-ink text-stone-bg py-2.5 text-sm font-medium hover:bg-ink-soft transition-colors disabled:opacity-50"
            >
              {busy ? "Please wait…" : mode === "signin" ? "Sign in" : "Create account"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}