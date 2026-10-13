import Link from "next/link";

const ingest = [
  ["Upload", "PDF, image, or text"],
  ["Router", "Which kind of file is this?"],
  ["Chunk", "Semantic, fixed, or sentence"],
  ["LaTeX", "Image regions become equations"],
  ["Embed", "Gemini text-embedding-004"],
  ["Store", "pgvector in Supabase"],
];

const query = [
  ["Ask", "A message in a chat"],
  ["Route", "Library, web, or pretrained"],
  ["Embed", "Same model as ingestion"],
  ["Search", "Top chunks, then a rerank"],
  ["Write", "Gemini, with the passages"],
  ["Cite", "The chunks the answer used"],
];

export default function Home() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 py-10 sm:px-10">
      <header className="flex items-center justify-between gap-4">
        <p className="font-serif text-2xl text-ink">RCOS Reference</p>
        <div className="flex gap-2">
          <Link
            href="/login"
            className="rounded-full px-4 py-2 text-sm text-ink hover:bg-white"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="rounded-full bg-accent px-4 py-2 text-sm text-white hover:bg-[#841f1f]"
          >
            Create account
          </Link>
        </div>
      </header>

      <section className="mt-16 max-w-3xl">
        <p className="text-sm tracking-[0.16em] text-muted uppercase">Research library</p>
        <h1 className="mt-3 font-serif text-5xl leading-[1.05] text-ink sm:text-6xl">
          Retrieval that shows its work.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
          Keep notes and files in folders, then ask questions against that
          corpus. Every answer names the chunks it used.
        </p>
      </section>

      <section className="mt-14 grid gap-6 lg:grid-cols-2">
        <Flow title="Ingestion" steps={ingest} />
        <Flow title="Query" steps={query} />
      </section>
    </main>
  );
}

function Flow({ title, steps }: { title: string; steps: string[][] }) {
  return (
    <article className="rounded-3xl border border-line bg-paper-2 p-6">
      <h2 className="font-serif text-3xl text-ink">{title}</h2>
      <ol className="mt-5 grid gap-3">
        {steps.map(([name, detail], index) => (
          <li key={name} className="grid grid-cols-[2rem_1fr] gap-3">
            <span className="font-mono text-sm text-accent">{index + 1}</span>
            <span>
              <span className="block text-sm font-medium text-ink">{name}</span>
              <span className="block text-sm text-muted">{detail}</span>
            </span>
          </li>
        ))}
      </ol>
    </article>
  );
}
