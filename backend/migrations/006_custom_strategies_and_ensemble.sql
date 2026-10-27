-- US-21: strategies created by the student (a base strategy + validated parameters)
create table if not exists public.custom_strategies (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  name text not null,
  base_strategy text not null check (base_strategy in ('SMA', 'RSI', 'BOLLINGER', 'MOMENTUM')),
  params jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);

alter table public.custom_strategies enable row level security;

create policy "Users manage their own custom strategies"
  on public.custom_strategies for all
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

-- A configuration keeps a SNAPSHOT of the custom strategies it uses, so the simulation can be reproduced
-- even if the student edits or deletes the strategy later.
alter table public.backtest_configurations add column if not exists custom_strategies jsonb not null default '[]'::jsonb;

-- US-24: score limit of the ensemble (NULL = default 0.1)
alter table public.backtest_configurations add column if not exists ensemble_threshold double precision
  check (ensemble_threshold is null or ensemble_threshold > 0);

-- US-24: full breakdown of each ensemble decision (regime, weights, component signals, blended score)
alter table public.simulation_decisions add column if not exists breakdown jsonb;
