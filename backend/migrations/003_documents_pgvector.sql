-- US-33 / US-34 / US-30: knowledge base with pgvector.
-- Run once in the Supabase SQL editor.

create extension if not exists vector;

-- One row per uploaded file. user_id NULL = shared base document (e.g. the trading glossary).
create table if not exists public.documents (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid references auth.users(id) on delete cascade,
    filename    text not null,
    file_type   text not null check (file_type in ('pdf', 'txt', 'md', 'csv', 'docx')),
    size_bytes  integer not null,
    status      text not null default 'processing' check (status in ('processing', 'ready', 'failed')),
    chunk_count integer not null default 0,
    error       text,
    created_at  timestamptz not null default now()
);

-- One row per chunk, always linked to the document it came from (needed to cite sources).
-- 768 = output size of nomic-embed-text. If the embedding model changes, this number must change.
create table if not exists public.document_chunks (
    id          uuid primary key default gen_random_uuid(),
    document_id uuid not null references public.documents(id) on delete cascade,
    user_id     uuid references auth.users(id) on delete cascade,
    chunk_index integer not null,
    content     text not null,
    page        integer,
    embedding   vector(768) not null,
    created_at  timestamptz not null default now()
);

create index if not exists documents_user_idx        on public.documents (user_id);
create index if not exists document_chunks_doc_idx   on public.document_chunks (document_id);
-- Approximate nearest-neighbour index for cosine distance.
create index if not exists document_chunks_embedding_idx
    on public.document_chunks using hnsw (embedding vector_cosine_ops);

-- Row level security: Supabase exposes every public table through its REST API, so close the door.
-- The backend uses the secret key (bypasses RLS) and always filters by user_id itself.
alter table public.documents       enable row level security;
alter table public.document_chunks enable row level security;

create policy "read own or shared documents" on public.documents
    for select to authenticated using (user_id = auth.uid() or user_id is null);
create policy "delete own documents" on public.documents
    for delete to authenticated using (user_id = auth.uid());
create policy "read own or shared chunks" on public.document_chunks
    for select to authenticated using (user_id = auth.uid() or user_id is null);

-- Similarity search. similarity = 1 - cosine distance (1.0 identical, 0.0 unrelated).
-- Returns only chunks the user may see (own + shared) that reach the threshold.
create or replace function public.match_document_chunks(
    query_embedding vector(768),
    p_user_id       uuid,
    match_threshold float,
    match_count     int
)
returns table (
    id uuid,
    document_id uuid,
    filename text,
    chunk_index int,
    page int,
    content text,
    similarity float
)
language sql stable
as $$
    select c.id, c.document_id, d.filename, c.chunk_index, c.page, c.content,
           1 - (c.embedding <=> query_embedding) as similarity
    from public.document_chunks c
    join public.documents d on d.id = c.document_id
    where (c.user_id = p_user_id or c.user_id is null)
      and d.status = 'ready'
      and 1 - (c.embedding <=> query_embedding) >= match_threshold
    order by c.embedding <=> query_embedding
    limit match_count;
$$;

-- Only the backend (service role) may call it.
revoke execute on function public.match_document_chunks(vector, uuid, float, int)
    from public, anon, authenticated;
