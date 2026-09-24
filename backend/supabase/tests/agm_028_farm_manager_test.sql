-- AGM-028 tree constraints, ordering, grants, and farm isolation.

insert into auth.users(id) values
  ('28282828-2828-4828-8828-282828282811'),
  ('28282828-2828-4828-8828-282828282812'),
  ('28282828-2828-4828-8828-282828282813');

insert into public.farms(id, name) values
  ('28282828-2828-4828-8828-282828282801', 'Farm A'),
  ('28282828-2828-4828-8828-282828282802', 'Farm B'),
  ('28282828-2828-4828-8828-282828282803', 'Empty farm');

insert into public.farm_memberships(farm_id, user_id, role) values
  ('28282828-2828-4828-8828-282828282801', '28282828-2828-4828-8828-282828282811', 'owner'),
  ('28282828-2828-4828-8828-282828282801', '28282828-2828-4828-8828-282828282812', 'member'),
  ('28282828-2828-4828-8828-282828282802', '28282828-2828-4828-8828-282828282813', 'owner');

set role authenticated;
select set_config('request.jwt.claim.sub', '28282828-2828-4828-8828-282828282811', false);

insert into public.trees(id, farm_id, label, grid_row, grid_column) values
  ('28282828-2828-4828-8828-282828282821', '28282828-2828-4828-8828-282828282801', 'Tree B2', 2, 2),
  ('28282828-2828-4828-8828-282828282822', '28282828-2828-4828-8828-282828282801', 'Tree A2', 1, 2),
  ('28282828-2828-4828-8828-282828282823', '28282828-2828-4828-8828-282828282801', 'Tree A1', 1, 1);

do $$
declare
  ordered_labels text;
begin
  select string_agg(label, ',' order by grid_row, grid_column, id)
    into ordered_labels
  from public.trees
  where farm_id = '28282828-2828-4828-8828-282828282801';
  if ordered_labels <> 'Tree A1,Tree A2,Tree B2' then
    raise exception 'tree ordering is not deterministic: %', ordered_labels;
  end if;
end;
$$;

do $$
begin
  begin
    insert into public.trees(farm_id, label, grid_row, grid_column)
    values ('28282828-2828-4828-8828-282828282801', 'Duplicate A1', 1, 1);
    raise exception 'duplicate farm position accepted';
  exception when unique_violation then null;
  end;
  begin
    insert into public.trees(farm_id, label, grid_row, grid_column)
    values ('28282828-2828-4828-8828-282828282801', 'Invalid row', 0, 3);
    raise exception 'invalid row accepted';
  exception when check_violation then null;
  end;
  begin
    insert into public.trees(farm_id, label, grid_row, grid_column)
    values ('28282828-2828-4828-8828-282828282801', 'Invalid column', 3, 100);
    raise exception 'invalid column accepted';
  exception when check_violation then null;
  end;
end;
$$;

-- The same grid position is valid in another farm.
reset role;
set role service_role;
do $$
begin
  begin
    insert into public.trees(farm_id, label, grid_row, grid_column)
    values ('ffffffff-ffff-4fff-8fff-ffffffffffff', 'Missing farm', 1, 1);
    raise exception 'missing farm accepted';
  exception when foreign_key_violation then null;
  end;
end;
$$;
insert into public.trees(id, farm_id, label, grid_row, grid_column)
values ('28282828-2828-4828-8828-282828282824', '28282828-2828-4828-8828-282828282802', 'Farm B A1', 1, 1);
reset role;

-- Member can read only Farm A and cannot mutate it.
set role authenticated;
select set_config('request.jwt.claim.sub', '28282828-2828-4828-8828-282828282812', false);
do $$
begin
  if (select count(*) from public.trees) <> 3 then
    raise exception 'member read or cross-farm isolation failed';
  end if;
  if (select count(*) from public.trees where farm_id = '28282828-2828-4828-8828-282828282803') <> 0 then
    raise exception 'empty farm did not return an empty set';
  end if;
  begin
    insert into public.trees(farm_id, label, grid_row, grid_column)
    values ('28282828-2828-4828-8828-282828282801', 'Member insert', 3, 1);
    raise exception 'member insert accepted';
  exception when insufficient_privilege then null;
  end;
end;
$$;
update public.trees set label = 'Member update';
delete from public.trees;

do $$
begin
  if exists (select 1 from public.trees where label = 'Member update') then
    raise exception 'member update accepted';
  end if;
  if (select count(*) from public.trees) <> 3 then
    raise exception 'member delete accepted';
  end if;
end;
$$;

-- Farm A owner cannot read or write Farm B.
select set_config('request.jwt.claim.sub', '28282828-2828-4828-8828-282828282811', false);
do $$
begin
  if exists (
    select 1 from public.trees
    where farm_id = '28282828-2828-4828-8828-282828282802'
  ) then
    raise exception 'cross-farm read accepted';
  end if;
  begin
    insert into public.trees(farm_id, label, grid_row, grid_column)
    values ('28282828-2828-4828-8828-282828282802', 'Cross farm', 2, 1);
    raise exception 'cross-farm insert accepted';
  exception when insufficient_privilege then null;
  end;
  begin
    update public.trees
    set farm_id = '28282828-2828-4828-8828-282828282802'
    where id = '28282828-2828-4828-8828-282828282823';
    raise exception 'cross-farm move accepted';
  exception when insufficient_privilege then null;
  end;
end;
$$;
update public.trees set label = 'Cross-farm update'
where id = '28282828-2828-4828-8828-282828282824';
delete from public.trees
where id = '28282828-2828-4828-8828-282828282824';

reset role;
set role service_role;
do $$
begin
  if not exists (
    select 1 from public.trees
    where id = '28282828-2828-4828-8828-282828282824'
      and label = 'Farm B A1'
  ) then
    raise exception 'cross-farm update or delete escaped RLS';
  end if;
end;
$$;
reset role;

-- Anonymous clients have no table privileges.
set role anon;
do $$
begin
  begin
    perform count(*) from public.trees;
    raise exception 'anonymous read accepted';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into public.trees(farm_id, label, grid_row, grid_column)
    values ('28282828-2828-4828-8828-282828282801', 'Anonymous', 3, 1);
    raise exception 'anonymous insert accepted';
  exception when insufficient_privilege then null;
  end;
  begin
    update public.trees set label = 'Anonymous update';
    raise exception 'anonymous update accepted';
  exception when insufficient_privilege then null;
  end;
  begin
    delete from public.trees;
    raise exception 'anonymous delete accepted';
  exception when insufficient_privilege then null;
  end;
end;
$$;
reset role;

-- Owners can update and delete their own trees.
set role authenticated;
select set_config('request.jwt.claim.sub', '28282828-2828-4828-8828-282828282811', false);
update public.trees set label = 'Updated A1'
where id = '28282828-2828-4828-8828-282828282823';
delete from public.trees
where id = '28282828-2828-4828-8828-282828282821';
do $$
begin
  if not exists (select 1 from public.trees where label = 'Updated A1') then
    raise exception 'owner update failed';
  end if;
  if exists (
    select 1 from public.trees
    where id = '28282828-2828-4828-8828-282828282821'
  ) then
    raise exception 'owner delete failed';
  end if;
end;
$$;
reset role;
