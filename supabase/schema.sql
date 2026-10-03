-- Cutroom schema. Run once in the Supabase SQL editor (or psql) on a fresh project.
create extension if not exists pgcrypto;

-- one row per user (anonymous or signed-in); agents authenticate with api_key
create table if not exists accounts (
  user_id uuid primary key references auth.users on delete cascade,
  credits int not null default 3,
  api_key text unique not null default 'cr_' || encode(gen_random_bytes(18), 'hex'),
  stripe_customer text,
  created_at timestamptz not null default now()
);

create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  owner uuid references auth.users on delete set null,
  topic text not null,
  length_s int not null default 60,
  want_4k boolean not null default false,
  source text not null default 'web',            -- web | mcp
  is_public boolean not null default true,         -- shows in the gallery
  status text not null default 'queued',           -- queued | running | done | failed
  stage text,                                      -- script | footage | moments | graphics | voice | assemble | critique | upscale | done
  progress int not null default 0,                 -- 0..100
  title text,
  logline text,
  script jsonb,                                    -- director's timeline (segments)
  critique jsonb,                                  -- list of critique rounds
  credits jsonb,                                   -- license ledger: [{title, channel, url, license, used:[start,end]}]
  video_url text,                                  -- 1080p cut
  video_4k_url text,
  poster_url text,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- live feed for the studio UI (Realtime)
create table if not exists events (
  id bigserial primary key,
  project_id uuid not null references projects on delete cascade,
  kind text not null,          -- stage | thought | tool | clip | graphic | cut | critique | error | done
  message text not null,
  data jsonb,
  created_at timestamptz not null default now()
);
create index if not exists events_project on events (project_id, id);

-- every shot considered or used, with its license
create table if not exists clips (
  id bigserial primary key,
  project_id uuid not null references projects on delete cascade,
  youtube_id text not null,
  title text, channel text, license text, url text,
  start_s real, end_s real, description text,
  used boolean not null default false,
  created_at timestamptz not null default now()
);

alter table accounts enable row level security;
alter table projects enable row level security;
alter table events enable row level security;
alter table clips enable row level security;

drop policy if exists "own account" on accounts;
create policy "own account" on accounts for select using (user_id = auth.uid());
drop policy if exists "public or own projects" on projects;
create policy "public or own projects" on projects for select using (is_public or owner = auth.uid());
drop policy if exists "events of visible projects" on events;
create policy "events of visible projects" on events for select
  using (exists (select 1 from projects p where p.id = project_id and (p.is_public or p.owner = auth.uid())));
drop policy if exists "clips of visible projects" on clips;
create policy "clips of visible projects" on clips for select
  using (exists (select 1 from projects p where p.id = project_id and (p.is_public or p.owner = auth.uid())));
-- all writes go through the service role (web API routes and the worker)

-- spend a credit atomically; returns false when the account is empty
create or replace function spend_credits(uid uuid, n int) returns boolean language sql as $$
  update accounts set credits = credits - n where user_id = uid and credits >= n returning true;
$$;

create or replace function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;
drop trigger if exists projects_touch on projects;
create trigger projects_touch before update on projects for each row execute function touch_updated_at();

-- Realtime for the studio view
do $$ begin
  alter publication supabase_realtime add table projects;
exception when duplicate_object then null; end $$;
do $$ begin
  alter publication supabase_realtime add table events;
exception when duplicate_object then null; end $$;

-- public bucket for clips, graphics and renders
insert into storage.buckets (id, name, public) values ('media', 'media', true) on conflict (id) do nothing;
