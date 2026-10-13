"use client";

import { apiFetch } from "@/lib/api";
import { clearSession, loadPerson, loadSession, savePerson } from "@/lib/session";
import type {
  AnswerResult,
  ChatDetail,
  ChatMessage,
  ChatSummary,
  IngestResult,
  Library,
  Person,
} from "@/lib/types";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";

const MODES: Record<string, string> = {
  rag_only: "RAG only",
  rag_web: "RAG + web",
  rag_pretrained: "RAG + pretrained",
};

export function Workspace() {
  const router = useRouter();
  const [person, setPerson] = useState<Person | null>(null);
  const [library, setLibrary] = useState<Library>({ folders: [], items: [] });
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatName, setChatName] = useState("New chat");
  const [folderId, setFolderId] = useState<string>("");
  const [panel, setPanel] = useState<"library" | "chat">("chat");
  const [note, setNote] = useState("");
  const [draft, setDraft] = useState("");
  const [folderName, setFolderName] = useState("");
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState<"upload" | "note" | "send" | "">("");

  const loadLibrary = useCallback(async () => {
    const data = await apiFetch<Library>("/api/library");
    setLibrary(data);
    setFolderId((current) => current || data.folders[0]?.id || "");
  }, []);

  const loadChats = useCallback(async () => {
    const data = await apiFetch<{ chats: ChatSummary[] }>("/api/chats");
    setChats(data.chats);
  }, []);

  const openChat = useCallback(async (id: string) => {
    const data = await apiFetch<ChatDetail>(`/api/chats/${id}`);
    setChatId(data.id);
    setChatName(data.chat_name);
    setMessages(data.messages);
    setPanel("chat");
  }, []);

  useEffect(() => {
    if (!loadSession()) {
      router.replace("/login");
      return;
    }
    const cached = loadPerson();
    if (cached) setPerson(cached);
    let cancelled = false;
    (async () => {
      try {
        const me = await apiFetch<Person>("/api/auth/me");
        if (cancelled) return;
        setPerson(me);
        savePerson(me);
        await Promise.all([loadLibrary(), loadChats()]);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load the library.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadChats, loadLibrary, router]);

  const itemsInFolder = useMemo(
    () => library.items.filter((item) => !folderId || item.folder_id === folderId),
    [folderId, library.items],
  );

  async function run(kind: "upload" | "note" | "send", action: () => Promise<void>) {
    setError("");
    setBusy(kind);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setBusy("");
    }
  }

  async function onUpload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const input = form.elements.namedItem("file");
    const file = input instanceof HTMLInputElement ? input.files?.[0] : undefined;
    if (!file) return;
    const body = new FormData();
    body.set("file", file);
    if (folderId) body.set("folder_id", folderId);
    await run("upload", async () => {
      const result = await apiFetch<IngestResult>("/api/library/files", {
        method: "POST",
        body,
      });
      setStatus(
        `${result.name}: ${result.document_kind} · ${result.strategy} · ${result.chunk_count} chunks`,
      );
      form.reset();
      await loadLibrary();
    });
  }

  async function onNote(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = note.trim();
    if (!data) return;
    await run("note", async () => {
      const result = await apiFetch<IngestResult>("/api/library/notes", {
        method: "POST",
        body: JSON.stringify({ data, folder_id: folderId || null }),
      });
      setStatus(`Note: ${result.strategy} · ${result.chunk_count} chunks`);
      setNote("");
      await loadLibrary();
    });
  }

  async function onFolder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = folderName.trim();
    if (!name) return;
    setError("");
    try {
      const folder = await apiFetch<{ id: string }>("/api/library/folders", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      setFolderName("");
      await loadLibrary();
      setFolderId(folder.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the folder.");
    }
  }

  async function onNewChat() {
    setError("");
    try {
      const chat = await apiFetch<ChatSummary>("/api/chats", {
        method: "POST",
        body: JSON.stringify({ chat_name: "New chat" }),
      });
      await loadChats();
      await openChat(chat.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start a chat.");
    }
  }

  async function onDeleteChat(id: string) {
    setError("");
    try {
      await apiFetch(`/api/chats/${id}`, { method: "DELETE" });
      if (chatId === id) {
        setChatId(null);
        setMessages([]);
        setChatName("New chat");
      }
      await loadChats();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete the chat.");
    }
  }

  async function onDeleteItem(item: Library["items"][number]) {
    setError("");
    const path = item.kind === "file" ? `/api/library/files/${item.id}` : `/api/library/notes/${item.id}`;
    try {
      await apiFetch(path, { method: "DELETE" });
      await loadLibrary();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete that item.");
    }
  }

  async function onSend(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message) return;
    await run("send", async () => {
      let id = chatId;
      if (!id) {
        const chat = await apiFetch<ChatSummary>("/api/chats", {
          method: "POST",
          body: JSON.stringify({ chat_name: "New chat" }),
        });
        id = chat.id;
        setChatId(id);
      }
      const result = await apiFetch<AnswerResult>(`/api/chats/${id}/messages`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });
      setDraft("");
      setStatus(`${MODES[result.mode] ?? result.mode} — ${result.router_reason}`);
      await loadChats();
      const detail = await apiFetch<ChatDetail>(`/api/chats/${id}`);
      setChatName(detail.chat_name);
      setMessages(detail.messages);
    });
  }

  function signOut() {
    clearSession();
    router.replace("/login");
  }

  const name = person ? `${person.first_name} ${person.last_name}`.trim() : "Signed in";

  return (
    <div className="flex h-dvh flex-col bg-paper text-ink md:flex-row">
      <aside
        className={`${panel === "library" ? "flex" : "hidden"} min-h-0 w-full flex-col bg-rail text-[#f4efe6] md:flex md:w-[340px] md:shrink-0`}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <p className="font-serif text-2xl">Reference</p>
          <button type="button" className="text-sm text-[#d9cfc2] md:hidden" onClick={() => setPanel("chat")}>
            Chat
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 pb-4">
          <section>
            <div className="mb-2 flex items-center justify-between px-1">
              <h2 className="text-xs tracking-[0.14em] text-[#b7aa9c] uppercase">Library</h2>
            </div>
            <form onSubmit={onFolder} className="mb-3 flex gap-2">
              <input
                value={folderName}
                onChange={(event) => setFolderName(event.target.value)}
                placeholder="New folder"
                aria-label="Folder name"
                className="h-9 min-w-0 flex-1 rounded-lg border border-white/10 bg-rail-2 px-3 text-sm outline-none"
              />
              <button type="submit" className="rounded-lg px-3 text-sm text-[#f4efe6] hover:bg-white/10">
                Add
              </button>
            </form>
            <div className="flex flex-wrap gap-2">
              {library.folders.map((folder) => (
                <button
                  key={folder.id}
                  type="button"
                  onClick={() => setFolderId(folder.id)}
                  className={`rounded-full px-3 py-1 text-sm ${folder.id === folderId ? "bg-[#f4efe6] text-rail" : "bg-rail-2 text-[#e7ddd0]"}`}
                >
                  {folder.name}
                </button>
              ))}
            </div>
            <ul className="mt-3 space-y-1">
              {itemsInFolder.length === 0 && (
                <li className="px-1 text-sm text-[#b7aa9c]">Nothing in this folder yet.</li>
              )}
              {itemsInFolder.map((item) => (
                <li key={`${item.kind}-${item.id}`} className="flex items-start gap-2 rounded-lg px-2 py-2 hover:bg-white/5">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{item.name}</p>
                    <p className="text-xs text-[#b7aa9c]">
                      {item.kind === "file" ? "File" : "Note"} · {item.chunk_count} chunks
                    </p>
                  </div>
                  <button
                    type="button"
                    className="text-xs text-[#b7aa9c] hover:text-white"
                    onClick={() => onDeleteItem(item)}
                    aria-label={`Delete ${item.name}`}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <form onSubmit={onUpload} className="mt-3 space-y-2">
              <input
                name="file"
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.txt,.md,.csv,.json,application/pdf,text/plain"
                aria-label="Upload a file"
                className="block w-full text-xs text-[#d9cfc2] file:mr-3 file:rounded-full file:border-0 file:bg-[#f4efe6] file:px-3 file:py-1.5 file:text-xs file:text-rail"
              />
              <button
                type="submit"
                disabled={busy === "upload"}
                className="h-9 w-full rounded-full bg-[#f4efe6] text-sm text-rail disabled:opacity-60"
              >
                {busy === "upload" ? "Embedding…" : "Upload and embed"}
              </button>
            </form>
            <form onSubmit={onNote} className="mt-3 space-y-2">
              <textarea
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={3}
                placeholder="Paste a note"
                aria-label="Note"
                className="w-full resize-none rounded-xl border border-white/10 bg-rail-2 px-3 py-2 text-sm outline-none"
              />
              <button
                type="submit"
                disabled={busy === "note"}
                className="h-9 w-full rounded-full border border-white/15 text-sm disabled:opacity-60"
              >
                {busy === "note" ? "Embedding…" : "Save note"}
              </button>
            </form>
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between px-1">
              <h2 className="text-xs tracking-[0.14em] text-[#b7aa9c] uppercase">Chats</h2>
              <button type="button" onClick={onNewChat} className="text-sm text-[#f4efe6]">
                New
              </button>
            </div>
            <ul className="space-y-1">
              {chats.map((chat) => (
                <li key={chat.id} className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => openChat(chat.id)}
                    className={`min-w-0 flex-1 truncate rounded-lg px-2 py-2 text-left text-sm ${chat.id === chatId ? "bg-white/10" : "hover:bg-white/5"}`}
                  >
                    {chat.chat_name}
                  </button>
                  <button
                    type="button"
                    className="px-1 text-xs text-[#b7aa9c]"
                    onClick={() => onDeleteChat(chat.id)}
                    aria-label={`Delete ${chat.chat_name}`}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <div className="flex items-center justify-between gap-3 border-t border-white/10 px-4 py-4">
          <div className="min-w-0">
            <p className="truncate text-sm">{name}</p>
            <p className="truncate text-xs text-[#b7aa9c]">
              {person?.is_admin ? "Admin · " : ""}
              {person?.email}
            </p>
          </div>
          <button type="button" onClick={signOut} className="text-sm text-[#f4efe6]">
            Sign out
          </button>
        </div>
      </aside>

      <section className={`${panel === "chat" ? "flex" : "hidden"} min-h-0 min-w-0 flex-1 flex-col md:flex`}>
        <header className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <button type="button" className="text-sm text-muted md:hidden" onClick={() => setPanel("library")}>
              Library
            </button>
            <h1 className="font-serif text-2xl">{chatId ? chatName : "Ask the library"}</h1>
          </div>
        </header>

        {(error || status) && (
          <p className={`px-5 py-3 text-sm ${error ? "text-accent" : "text-moss"}`} role={error ? "alert" : "status"}>
            {error || status}
          </p>
        )}

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-6">
          {messages.length === 0 && (
            <div className="mx-auto max-w-xl pt-10">
              <p className="font-serif text-4xl leading-tight">What should the library answer?</p>
              <p className="mt-4 leading-7 text-muted">
                Upload a PDF, an image, or a note. The query router decides whether to stay
                inside the corpus, add the web, or use pretrained knowledge. Answers cite the chunks they used.
              </p>
            </div>
          )}
          {messages.map((message) => (
            <article key={message.message_id} className="mx-auto max-w-3xl">
              <p className="text-xs tracking-[0.14em] text-muted uppercase">
                {message.role === "user" ? "You" : MODES[message.query_mode || ""] || "Reference"}
              </p>
              <p className="mt-2 whitespace-pre-wrap leading-7">{message.message}</p>
              {message.citations && message.citations.length > 0 && (
                <ul className="mt-3 grid gap-2">
                  {message.citations.map((citation) => (
                    <li key={citation.chunk_id} className="rounded-2xl border border-line bg-paper-2 px-4 py-3">
                      <p className="text-xs text-muted">
                        {citation.source}
                        {typeof citation.similarity === "number"
                          ? ` · ${Math.round(citation.similarity * 100)}% match`
                          : ""}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-ink">{citation.excerpt}</p>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>

        <form onSubmit={onSend} className="border-t border-line px-5 py-4">
          <div className="mx-auto flex max-w-3xl gap-2">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              rows={2}
              placeholder="Ask a question"
              aria-label="Message"
              className="min-w-0 flex-1 resize-none rounded-2xl border border-line bg-paper-2 px-4 py-3 outline-none ring-accent/30 focus:ring-2"
            />
            <button
              type="submit"
              disabled={busy === "send"}
              className="h-12 self-end rounded-full bg-accent px-5 text-sm text-white disabled:opacity-60"
            >
              {busy === "send" ? "Searching…" : "Send"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
