-- Columns used by the web app / plugin design (brief, aspect ratio, style). Safe to run more than once.
alter table projects add column if not exists brief text;
alter table projects add column if not exists aspect_ratio text not null default '16:9';
alter table projects add column if not exists style text;
alter table projects alter column topic drop not null;
