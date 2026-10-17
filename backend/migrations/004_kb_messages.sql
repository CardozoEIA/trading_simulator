-- Conversation history of the knowledge-base chat (US-30). Run once in the Supabase SQL editor.
create table if not exists public.kb_messages (
    id         bigint generated always as identity primary key,
    user_id    uuid not null references auth.users(id) on delete cascade,
    turn_id    uuid not null,
    role       text not null check (role in ('user', 'assistant')),
    content    text not null,
    refused    boolean not null default false,
    sources    jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists kb_messages_user_idx on public.kb_messages (user_id, id);

-- The backend uses the secret key (bypasses RLS) and filters by user_id; no policies = closed to the public API.
alter table public.kb_messages enable row level security;
