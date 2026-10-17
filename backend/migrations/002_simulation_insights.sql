-- US-26: proactive insights generated when a simulation finishes
create table if not exists public.simulation_insights (
  simulation_id uuid primary key references public.simulations(id) on delete cascade,
  status text not null check (status in ('PENDING', 'READY', 'FAILED')),
  insights jsonb,
  error text,
  generated_at timestamptz,
  updated_at timestamptz not null default now()
);

alter table public.simulation_insights enable row level security;

-- The backend uses the service role; this policy only matters for direct client reads.
create policy "Users read insights of their own simulations"
  on public.simulation_insights for select
  using (exists (
    select 1 from public.simulations s
    where s.id = simulation_id and s.user_id = auth.uid()
  ));
