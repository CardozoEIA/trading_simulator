-- US-25: persistent conversation memory for the simulation chat.
-- Safe to run more than once.
create table if not exists public.chat_messages (
  id bigint generated always as identity primary key,
  user_id uuid not null,
  simulation_id uuid not null references public.simulations(id) on delete cascade,
  turn_id uuid,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  route text,
  date text,
  embedding jsonb,
  created_at timestamptz not null default now()
);

-- For databases where an earlier version of this table already exists.
alter table public.chat_messages add column if not exists turn_id uuid;
alter table public.chat_messages add column if not exists embedding jsonb;

create index if not exists chat_messages_conversation_idx
  on public.chat_messages (simulation_id, user_id, turn_id);

alter table public.chat_messages enable row level security;

-- The backend uses the service role; this policy only matters for direct client reads.
drop policy if exists "Users read their own chat messages" on public.chat_messages;
create policy "Users read their own chat messages"
  on public.chat_messages for select
  using (user_id = auth.uid());
