-- AGM-028: farm tree inventory for the Farm Manager data boundary.
-- Health, CV inspection, telemetry, and irrigation remain separate concerns.

create table public.trees (
  id uuid primary key default pg_catalog.gen_random_uuid() check (
    id <> '00000000-0000-0000-0000-000000000000'
  ),
  farm_id uuid not null references public.farms(id) on delete cascade,
  label text not null check (
    btrim(label) <> '' and char_length(btrim(label)) <= 120
  ),
  grid_row smallint not null check (grid_row between 1 and 26),
  grid_column smallint not null check (grid_column between 1 and 99),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (farm_id, grid_row, grid_column)
);

create index trees_farm_order_idx
  on public.trees(farm_id, grid_row, grid_column, id);

create trigger trees_set_updated_at
before update on public.trees
for each row execute function public.set_updated_at();

alter table public.trees enable row level security;

revoke all on table public.trees from public, anon, authenticated;
grant all on table public.trees to service_role;
grant select, insert, update, delete on table public.trees to authenticated;

create policy trees_select_member
on public.trees for select to authenticated
using (private.is_farm_member(farm_id));

create policy trees_insert_owner
on public.trees for insert to authenticated
with check (private.is_farm_owner(farm_id));

create policy trees_update_owner
on public.trees for update to authenticated
using (private.is_farm_owner(farm_id))
with check (private.is_farm_owner(farm_id));

create policy trees_delete_owner
on public.trees for delete to authenticated
using (private.is_farm_owner(farm_id));

comment on table public.trees is
  'Farm-scoped tree inventory. AGM-028 deliberately stores no inferred health or CV state.';
comment on column public.trees.label is
  'Mutable user-facing name; never used as the technical identity.';
comment on column public.trees.grid_row is
  'One-based row (1=A through 26=Z) used with grid_column for stable display ordering.';
