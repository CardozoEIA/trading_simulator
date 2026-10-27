-- US-23: market regime labels, precalculated offline with a walk-forward schedule (see scripts/precalculate_regimes.py)
create table if not exists public.market_regimes (
  asset text not null,
  date date not null,
  algorithm_version text not null,      -- e.g. 'wf-regime-v1'; bump it when the method changes
  regime text not null check (regime in ('HIGH_VOLATILITY', 'TRENDING', 'RANGE_BOUND')),
  volatility double precision not null,
  trend_strength double precision not null,
  checkpoint_date date not null,        -- the checkpoint whose model (trained on earlier data only) produced the label
  model_version text not null,          -- algorithm_version || '@' || checkpoint_date
  created_at timestamptz not null default now(),
  primary key (asset, date, algorithm_version)
);

create index if not exists market_regimes_asset_date_idx on public.market_regimes (asset, date);

alter table public.market_regimes enable row level security;

-- Market data is the same for everybody: any signed-in user may read it. Only the backend writes.
create policy "Signed-in users read market regimes"
  on public.market_regimes for select
  using (auth.role() = 'authenticated');

-- The regime in effect is stored next to the technical signals of each simulation.
alter table public.simulation_signals add column if not exists regime text;
alter table public.simulation_signals add column if not exists regime_model_version text;
