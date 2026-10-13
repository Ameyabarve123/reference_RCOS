-- RCOS RAG schema
-- Maps the Architecture/ER_diagram.pdf relational model onto Postgres + pgvector.
--
-- PersonStoresFilesText is intentionally omitted: the diagram marks it redundant
-- with FolderContainingFilesText.
--
-- Practical columns the handwritten model does not list, but the app needs:
--   folder.person_uid          empty folders still need an owner
--   files.filename, content_type
--   messages.role, query_mode  distinguish turns and the query-router mode
--   chunk_references.message_id, similarity
--                                citations belong to the answer that used them
--
-- Run this once in the Supabase SQL editor.
-- SUPABASE_KEY on the backend must be the secret / service-role key.

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Entities
-- ---------------------------------------------------------------------------

create table if not exists person (
  uid uuid primary key,
  first_name text not null default '',
  last_name text not null default '',
  email text not null unique,
  phone_number text unique,
  timestamp timestamptz not null default now(),
  is_admin boolean not null default false
);

create table if not exists folder (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  timestamp timestamptz not null default now(),
  person_uid uuid not null references person (uid) on delete cascade
);

create table if not exists texts (
  id uuid primary key default gen_random_uuid(),
  data text not null,
  timestamp timestamptz not null default now()
);

create table if not exists files (
  id uuid primary key default gen_random_uuid(),
  s3_key text,
  url text,
  timestamp timestamptz not null default now(),
  filename text not null default 'upload',
  content_type text
);

create table if not exists chats (
  id uuid primary key default gen_random_uuid(),
  chat_name text not null default 'New chat',
  timestamp timestamptz not null default now(),
  person_uid uuid not null references person (uid) on delete cascade
);

create table if not exists messages (
  message_id uuid primary key default gen_random_uuid(),
  chat_id uuid not null references chats (id) on delete cascade,
  timestamp timestamptz not null default now(),
  message text not null,
  role text not null check (role in ('user', 'assistant')),
  query_mode text check (query_mode in ('rag_only', 'rag_web', 'rag_pretrained'))
);

create table if not exists ai_provider (
  id uuid primary key default gen_random_uuid(),
  name text not null unique
);

create table if not exists chunks (
  id uuid primary key default gen_random_uuid(),
  chunk text not null,
  file_id uuid references files (id) on delete cascade,
  text_id uuid references texts (id) on delete cascade,
  ai_provider_id uuid references ai_provider (id),
  timestamp timestamptz not null default now(),
  check (
    (file_id is not null and text_id is null)
    or (file_id is null and text_id is not null)
  )
);

-- References(ChunkId, ChatId), plus the message that cited the chunk.
create table if not exists chunk_references (
  chunk_id uuid not null references chunks (id) on delete cascade,
  chat_id uuid not null references chats (id) on delete cascade,
  message_id uuid not null references messages (message_id) on delete cascade,
  similarity real,
  primary key (chunk_id, message_id)
);

create table if not exists embeddings (
  id uuid primary key default gen_random_uuid(),
  -- text-embedding-004
  embedding vector(768) not null,
  timestamp timestamptz not null default now(),
  chunk_id uuid not null references chunks (id) on delete cascade
);

create table if not exists uses (
  ai_provider_id uuid not null references ai_provider (id) on delete cascade,
  embedding_id uuid not null references embeddings (id) on delete cascade,
  primary key (ai_provider_id, embedding_id)
);

create table if not exists folder_containing_files_text (
  id uuid primary key default gen_random_uuid(),
  person_uid uuid not null references person (uid) on delete cascade,
  text_id uuid references texts (id) on delete cascade,
  file_id uuid references files (id) on delete cascade,
  folder_id uuid not null references folder (id) on delete cascade,
  check (
    (text_id is not null and file_id is null)
    or (text_id is null and file_id is not null)
  )
);

create index if not exists folder_owner_idx on folder (person_uid);
create index if not exists chats_owner_idx on chats (person_uid, timestamp desc);
create index if not exists messages_chat_idx on messages (chat_id, timestamp);
create index if not exists chunks_file_idx on chunks (file_id);
create index if not exists chunks_text_idx on chunks (text_id);
create index if not exists embeddings_chunk_idx on embeddings (chunk_id);
create index if not exists link_owner_idx on folder_containing_files_text (person_uid, folder_id);
create index if not exists embeddings_vector_idx
  on embeddings using hnsw (embedding vector_cosine_ops);

insert into ai_provider (name)
values ('gemini')
on conflict (name) do nothing;

-- ---------------------------------------------------------------------------
-- Retrieval: top-k cosine search over the owner's chunks
-- ---------------------------------------------------------------------------

create or replace function match_chunks(
  query_embedding vector(768),
  match_count int,
  owner uuid
)
returns table (
  chunk_id uuid,
  chunk text,
  file_id uuid,
  text_id uuid,
  source_name text,
  similarity float
)
language sql
stable
as $$
  with ranked as (
    select distinct on (c.id)
      c.id as chunk_id,
      c.chunk,
      c.file_id,
      c.text_id,
      coalesce(
        f.filename,
        left(regexp_replace(t.data, '\s+', ' ', 'g'), 80)
      ) as source_name,
      (1 - (e.embedding <=> query_embedding))::float as similarity
    from embeddings e
    join chunks c on c.id = e.chunk_id
    left join files f on f.id = c.file_id
    left join texts t on t.id = c.text_id
    where exists (
      select 1
      from folder_containing_files_text link
      where link.person_uid = owner
        and (
          (c.file_id is not null and link.file_id = c.file_id)
          or (c.text_id is not null and link.text_id = c.text_id)
        )
    )
    order by c.id, e.embedding <=> query_embedding
  )
  select *
  from ranked
  order by similarity desc
  limit match_count;
$$;

do $$
begin
  execute 'revoke all on function match_chunks(vector, int, uuid) from public';
  execute 'grant execute on function match_chunks(vector, int, uuid) to service_role';
exception
  when others then
    raise notice 'Skipped match_chunks grants: %', sqlerrm;
end $$;

-- ---------------------------------------------------------------------------
-- Row level security. The backend uses the secret key and bypasses these.
-- They keep the anon/publishable key from reading another person's rows.
-- ---------------------------------------------------------------------------

alter table person enable row level security;
alter table folder enable row level security;
alter table texts enable row level security;
alter table files enable row level security;
alter table chats enable row level security;
alter table messages enable row level security;
alter table chunks enable row level security;
alter table chunk_references enable row level security;
alter table embeddings enable row level security;
alter table uses enable row level security;
alter table folder_containing_files_text enable row level security;
alter table ai_provider enable row level security;

drop policy if exists person_self on person;
create policy person_self on person
  for all to authenticated
  using (uid = auth.uid())
  with check (uid = auth.uid());

drop policy if exists folder_self on folder;
create policy folder_self on folder
  for all to authenticated
  using (person_uid = auth.uid())
  with check (person_uid = auth.uid());

drop policy if exists chats_self on chats;
create policy chats_self on chats
  for all to authenticated
  using (person_uid = auth.uid())
  with check (person_uid = auth.uid());

drop policy if exists messages_self on messages;
create policy messages_self on messages
  for all to authenticated
  using (
    exists (
      select 1 from chats
      where chats.id = messages.chat_id and chats.person_uid = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from chats
      where chats.id = messages.chat_id and chats.person_uid = auth.uid()
    )
  );

drop policy if exists link_self on folder_containing_files_text;
create policy link_self on folder_containing_files_text
  for all to authenticated
  using (person_uid = auth.uid())
  with check (person_uid = auth.uid());

drop policy if exists ai_provider_read on ai_provider;
create policy ai_provider_read on ai_provider
  for select to authenticated
  using (true);

-- Private object storage for uploads. s3_key on files points at this bucket.
do $$
begin
  insert into storage.buckets (id, name, public)
  values ('documents', 'documents', false)
  on conflict (id) do nothing;
exception
  when others then
    raise notice 'Skipped storage bucket creation: %', sqlerrm;
end $$;
