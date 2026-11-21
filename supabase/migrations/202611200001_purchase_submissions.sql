begin;

create table if not exists public.purchase_submissions (
    id uuid primary key default gen_random_uuid(),
    submitted_at timestamptz not null default now(),
    inputs jsonb not null check (jsonb_typeof(inputs) = 'object')
);

alter table public.purchase_submissions enable row level security;

revoke all privileges on table public.purchase_submissions
    from public, anon, authenticated, service_role;
grant insert on table public.purchase_submissions to service_role;

commit;
