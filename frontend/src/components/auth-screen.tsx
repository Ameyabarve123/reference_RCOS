"use client";

import { login, signup } from "@/lib/api";
import { loadSession } from "@/lib/session";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

type Mode = "login" | "signup";

export function AuthScreen({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (loadSession()) router.replace("/app");
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setPending(true);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") || "");
    const password = String(form.get("password") || "");
    try {
      if (mode === "login") {
        await login(email, password);
        router.push("/app");
        return;
      }
      const result = await signup({
        email,
        password,
        first_name: String(form.get("first_name") || ""),
        last_name: String(form.get("last_name") || ""),
        phone_number: String(form.get("phone_number") || ""),
      });
      if (result.confirmation_required) {
        setNotice("Check your email to confirm the account, then sign in.");
        return;
      }
      router.push("/app");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="grid min-h-dvh lg:grid-cols-[1.1fr_0.9fr]">
      <section className="hidden flex-col justify-between bg-rail px-12 py-10 text-[#f6f1e7] lg:flex">
        <p className="font-serif text-2xl">RCOS Reference</p>
        <div className="max-w-md">
          <h1 className="font-serif text-5xl leading-tight">
            Ask the library, and see the pages it used.
          </h1>
          <p className="mt-6 text-base leading-7 text-[#d9cfc2]">
            Uploads are routed, chunked, and embedded with Gemini. Questions
            search that same pgvector store and come back with citations.
          </p>
        </div>
        <p className="text-sm text-[#b7aa9c]">Next.js · FastAPI · LangChain · Supabase</p>
      </section>
      <section className="flex items-center justify-center px-6 py-16">
        <form onSubmit={onSubmit} className="w-full max-w-sm">
          <p className="font-serif text-3xl text-ink lg:hidden">RCOS Reference</p>
          <h2 className="mt-3 font-serif text-4xl text-ink">
            {mode === "login" ? "Sign in" : "Create an account"}
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            {mode === "login"
              ? "Use the email you registered with Supabase."
              : "This creates your Person record and a Library folder."}
          </p>

          {mode === "signup" && (
            <div className="mt-8 grid grid-cols-2 gap-3">
              <Field label="First name" name="first_name" autoComplete="given-name" />
              <Field label="Last name" name="last_name" autoComplete="family-name" />
            </div>
          )}
          <div className={mode === "signup" ? "mt-3" : "mt-8"}>
            <Field label="Email" name="email" type="email" autoComplete="email" />
          </div>
          {mode === "signup" && (
            <div className="mt-3">
              <Field
                label="Phone"
                name="phone_number"
                type="tel"
                autoComplete="tel"
                required={false}
              />
            </div>
          )}
          <div className="mt-3">
            <Field
              label="Password"
              name="password"
              type="password"
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </div>

          {error && (
            <p className="mt-4 text-sm text-accent" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="mt-4 text-sm text-moss" role="status">
              {notice}
            </p>
          )}

          <button
            type="submit"
            disabled={pending}
            className="mt-6 h-11 w-full rounded-full bg-accent text-sm font-medium text-white transition hover:bg-[#841f1f] disabled:opacity-60"
          >
            {pending ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
          <p className="mt-4 text-sm text-muted">
            {mode === "login" ? (
              <>
                New here?{" "}
                <a className="text-ink underline decoration-line underline-offset-4" href="/signup">
                  Create an account
                </a>
              </>
            ) : (
              <>
                Already registered?{" "}
                <a className="text-ink underline decoration-line underline-offset-4" href="/login">
                  Sign in
                </a>
              </>
            )}
          </p>
        </form>
      </section>
    </main>
  );
}

function Field({
  label,
  name,
  type = "text",
  autoComplete,
  required = true,
}: {
  label: string;
  name: string;
  type?: string;
  autoComplete?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm text-muted">
      {label}
      <input
        name={name}
        type={type}
        autoComplete={autoComplete}
        required={required}
        className="mt-1 h-11 w-full rounded-xl border border-line bg-paper-2 px-3 text-ink outline-none ring-accent/30 focus:ring-2"
      />
    </label>
  );
}
