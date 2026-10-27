-- US-31: traceability of the explanations. One row per explanation: the tools the agent called, what they
-- returned and what the self-verification step found.
create table if not exists public.agent_traces (
  id bigint generated always as identity primary key,
  simulation_id uuid not null references public.simulations(id) on delete cascade,
  user_id uuid not null,
  source text not null check (source in ('explain', 'chat')),
  date text,
  answer text not null,
  tool_calls jsonb not null default '[]'::jsonb,
  verification jsonb,
  created_at timestamptz not null default now()
);

create index if not exists agent_traces_lookup_idx
  on public.agent_traces (simulation_id, user_id, date, id desc);

alter table public.agent_traces enable row level security;

drop policy if exists "Users read their own agent traces" on public.agent_traces;
create policy "Users read their own agent traces"
  on public.agent_traces for select
  using (user_id = auth.uid());
