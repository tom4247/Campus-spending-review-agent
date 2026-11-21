begin;

create table if not exists public.purchase_reviews (
    id uuid primary key,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null,
    status text not null check (status in ('PENDING', 'APPROVE', 'DEFER', 'ESCALATE', 'UNAVAILABLE')),
    transcript jsonb not null check (jsonb_typeof(transcript) = 'array'),
    review jsonb check (jsonb_typeof(review) = 'object')
);

alter table public.purchase_reviews enable row level security;

revoke all privileges on table public.purchase_reviews
    from public, anon, authenticated, service_role;
grant select, insert, update on table public.purchase_reviews to service_role;

commit;
