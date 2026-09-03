--Ask My Docs - Database Schema

create extension if not exists vector
create extension if not exists pg_trgm --optional, helps fuzzy text search

--documents
create table if not exists(documents)(
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users(id) on delete cascade,
    file_name text not null,
    storage_path text not null,
    status text not null default 'pending'
        check (status in('pending','processing','ready','failed')),
    error_message text,
    page_count int,
    created at timestamptz not null default now(),
    updated at timestamptz not null default now()
);
create index if not exists idx_documents_owner_id on documents(owner_id);
create index if not exists idx_documents_status on documents(status);

--document chunks
create table if not exists document_chunks(
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    content text not null,
    chunk_index int not null,
    page_number int,
    embedding vector(384),
    content_tsv tsvector generated always as (to_tsvector('english',content)) stored,
    created at timestamptz not null default now()
);

create index if not exists idx_chunks_document_id on document_chunks(document_id);;
create index if not exists idx_chunks_embedding on document_chunks using hnsw(embedding vector_cosine_ops);
create index if not exists idx_chunks_content_tsv on document_chunks using gin(content_tsv);

-- 4. conversations
create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    owner_id uuid not null references auth.users(id) on delete cascade,
    title text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists idx_conversations_owner_id on conversations(owner_id);

-- 5. messages
create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check (role in ('user','assistant')),
    content text not null,
    is_answerable boolean,
    created_at timestamptz not null default now()
);
create index if not exists idx_messages_conversation_id on messages(conversation_id);

-- 6. citations
create table if not exists citations (
    id uuid primary key default gen_random_uuid(),
    message_id uuid not null references messages(id) on delete cascade,
    document_id uuid not null references documents(id) on delete cascade,
    chunk_id uuid references document_chunks(id) on delete set null,
    page_number int,
    snippet text,
    relevance_score float,
    created_at timestamptz not null default now()
);
create index if not exists idx_citations_message_id on citations(message_id);

-- 7. Row Level Security (defense in depth; backend uses the service-role
--    key which bypasses RLS, but this protects direct/anon-key access too)
alter table documents enable row level security;
alter table document_chunks enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;
alter table citations enable row level security;

drop policy if exists "own documents" on documents;
create policy "own documents" on documents
    for all using (owner_id = auth.uid());

drop policy if exists "own conversations" on conversations;
create policy "own conversations" on conversations
    for all using (owner_id = auth.uid());

drop policy if exists "chunks via owned document" on document_chunks;
create policy "chunks via owned document" on document_chunks
    for all using (
        document_id in (select id from documents where owner_id = auth.uid())
    );drop policy if exists "messages via owned conversation" on messages;
create policy "messages via owned conversation" on messages
    for all using (
        conversation_id in (select id from conversations where owner_id = auth.uid())
    );

drop policy if exists "citations via owned message" on citations;
create policy "citations via owned message" on citations
    for all using (
        message_id in (
            select m.id from messages m
            join conversations c on c.id = m.conversation_id
            where c.owner_id = auth.uid()
        )
    );

-- 8. RPC: vector similarity search
create or replace function match_document_chunks(
    p_document_ids uuid[],
    p_query_embedding vector(384),
    p_match_count int
)
returns table (
    id uuid, document_id uuid, content text,
    chunk_index int, page_number int, similarity float
)
language sql stable as $$
    select id, document_id, content, chunk_index, page_number,
           1 - (embedding <=> p_query_embedding) as similarity
    from document_chunks
    where document_id = any(p_document_ids)
    order by embedding <=> p_query_embedding
    limit p_match_count;
$$;

-- 9. RPC: BM25-style keyword search (Postgres full-text rank)
create or replace function search_document_chunks_bm25(
    p_document_ids uuid[],
    p_query text,
    p_match_count int
)
returns table (
    id uuid, document_id uuid, content text,
    chunk_index int, page_number int, rank float
)
language sql stable as $$
    select id, document_id, content, chunk_index, page_number,
           ts_rank(content_tsv, plainto_tsquery('english', p_query)) as rank
    from document_chunks
    where document_id = any(p_document_ids)
      and content_tsv @@ plainto_tsquery('english', p_query)
    order by rank desc
    limit p_match_count;
$$;

