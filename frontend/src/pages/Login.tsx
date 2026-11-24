import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  confirmSignIn,
  confirmSignUp,
  resendSignUpCode,
  signIn,
  signUp,
} from "aws-amplify/auth";
import { useAuth } from "../auth/AuthContext";
import { cognitoConfigured } from "../lib/amplify";

type Mode = "signin" | "signup" | "confirm" | "newpassword";

export function Login() {
  const { refresh, signedIn } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!cognitoConfigured) {
    return (
      <section className="home">
        <h1>Login</h1>
        <p className="lede">Cognito is not configured in this build.</p>
      </section>
    );
  }

  if (signedIn) {
    return (
      <section className="home">
        <h1>You are signed in</h1>
        <p className="lede">
          <Link to="/ai-settings">Go to AI settings</Link>
        </p>
      </section>
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      if (mode === "signin") {
        const result = await signIn({ username: email.trim(), password });
        if (result.nextStep.signInStep === "CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED") {
          setMode("newpassword");
          setStatus("Enter a new password to finish setting up your admin account.");
          return;
        }
        if (result.nextStep.signInStep === "DONE") {
          await refresh();
          navigate("/profile");
          return;
        }
        setStatus(`Extra step required: ${result.nextStep.signInStep}`);
        return;
      }
      if (mode === "newpassword") {
        await confirmSignIn({ challengeResponse: newPassword });
        await refresh();
        navigate("/profile");
        return;
      }
      if (mode === "signup") {
        await signUp({
          username: email.trim(),
          password,
          options: { userAttributes: { email: email.trim() } },
        });
        setMode("confirm");
        setStatus("Check your email for a confirmation code.");
        return;
      }
      await confirmSignUp({
        username: email.trim(),
        confirmationCode: code.trim(),
      });
      setMode("signin");
      setStatus("Confirmed — you can sign in now.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Auth failed");
    } finally {
      setBusy(false);
    }
  }

  async function onResend() {
    setBusy(true);
    setStatus(null);
    try {
      await resendSignUpCode({ username: email.trim() });
      setStatus("Code resent.");
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Resend failed");
    } finally {
      setBusy(false);
    }
  }

  const title =
    mode === "signup"
      ? "Sign up"
      : mode === "confirm"
        ? "Confirm"
        : mode === "newpassword"
          ? "Set new password"
          : "Log in";

  return (
    <section className="home">
      <p className="eyebrow">Account</p>
      <h1>{title}</h1>
      <p className="lede">
        Cognito email/password. After signup, confirm the code from your inbox.
        Invited admins: use the temporary password from email, then choose a new one.
      </p>

      <form className="settings-form" onSubmit={onSubmit}>
        {mode !== "newpassword" ? (
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="username"
            />
          </label>
        ) : null}

        {mode === "signin" || mode === "signup" ? (
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
            />
          </label>
        ) : null}

        {mode === "newpassword" ? (
          <label>
            New password
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
          </label>
        ) : null}

        {mode === "confirm" ? (
          <label>
            Confirmation code
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
              autoComplete="one-time-code"
            />
          </label>
        ) : null}

        <div className="settings-actions">
          <button type="submit" disabled={busy}>
            {mode === "signin"
              ? "Log in"
              : mode === "signup"
                ? "Sign up"
                : mode === "newpassword"
                  ? "Save password"
                  : "Confirm"}
          </button>
          {mode === "confirm" ? (
            <button type="button" disabled={busy} onClick={onResend}>
              Resend code
            </button>
          ) : null}
        </div>
      </form>

      <p className="settings-status">
        {mode === "signin" ? (
          <>
            No account?{" "}
            <button type="button" className="text-btn" onClick={() => setMode("signup")}>
              Sign up
            </button>
          </>
        ) : mode === "signup" ? (
          <>
            Have an account?{" "}
            <button type="button" className="text-btn" onClick={() => setMode("signin")}>
              Log in
            </button>
          </>
        ) : null}
      </p>
      {status ? <p className="settings-status">{status}</p> : null}
    </section>
  );
}
