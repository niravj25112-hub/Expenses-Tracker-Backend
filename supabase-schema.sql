drop table if exists expenses;
drop table if exists budgets;

create table expenses (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  title text not null,
  amount numeric not null check (amount > 0),
  type text not null default 'Individual',
  category text not null,
  expense_date text not null,
  created_at timestamp with time zone default now()
);

create table budgets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  month text not null,
  amount numeric not null check (amount > 0),
  created_at timestamp with time zone default now()
);

alter table expenses enable row level security;
alter table budgets enable row level security;

create policy "Users can read own expenses"
on expenses for select to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can insert own expenses"
on expenses for insert to authenticated
with check ((select auth.uid()) = user_id);

create policy "Users can delete own expenses"
on expenses for delete to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can read own budgets"
on budgets for select to authenticated
using ((select auth.uid()) = user_id);

create policy "Users can insert own budgets"
on budgets for insert to authenticated
with check ((select auth.uid()) = user_id);
