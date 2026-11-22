-- Flow: схема PostgreSQL. Применяется вручную и идемпотентно:
--   psql "$DATABASE_URL" -f db/schema.sql
-- Совместима с обычным Postgres (локально) и с Supabase.

-- ============================================================
-- people: участники (принятые заявки и добавленные вручную)
-- ============================================================
CREATE TABLE IF NOT EXISTS people (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    -- Last.fm-ник в каноничном написании. UNIQUE нужен для внешнего ключа из scrobbles.
    username       TEXT NOT NULL UNIQUE CHECK (username ~ '^[\w-]{1,64}$'),
    display_name   TEXT NOT NULL,
    -- Когда получено согласие. Без значения по умолчанию: код обязан передать его явно.
    -- У записей, перенесённых из SQLite, здесь время миграции (решение владельца).
    consent_at     TIMESTAMPTZ NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_synced_at TIMESTAMPTZ,                 -- NULL: ещё не загружали
    status         TEXT NOT NULL DEFAULT 'ok'
                   CHECK (status IN ('ok', 'private', 'not_found', 'error')),
    error          TEXT
);

-- ============================================================
-- scrobbles: история прослушиваний
-- ============================================================
CREATE TABLE IF NOT EXISTS scrobbles (
    -- В SQLite колонка называлась user. В Postgres user это зарезервированное слово,
    -- которое молча возвращает имя роли, поэтому колонка переименована.
    username TEXT   NOT NULL REFERENCES people(username) ON DELETE CASCADE ON UPDATE CASCADE,
    artist   TEXT   NOT NULL,
    track    TEXT   NOT NULL,
    ts       BIGINT NOT NULL,                   -- UNIX-секунды, как отдаёт Last.fm
    -- Естественный ключ: защита от дублей при повторной синхронизации и единственный индекс.
    -- Он же обслуживает MAX(ts) по человеку и join в списке людей (префикс username).
    PRIMARY KEY (username, ts, artist, track)
);

-- ============================================================
-- signup_requests: заявки друзей с публичной формы
-- ============================================================
CREATE TABLE IF NOT EXISTS signup_requests (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username   TEXT NOT NULL CHECK (username ~ '^[\w-]{1,64}$'),
    contact    TEXT CHECK (contact IS NULL OR char_length(contact) <= 100),  -- стирается после решения
    consent_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status     TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'approved', 'rejected')),
    decided_at TIMESTAMPTZ
);

-- Не больше одной ожидающей заявки на ник, без учёта регистра (как COLLATE NOCASE в SQLite).
CREATE UNIQUE INDEX IF NOT EXISTS signup_one_pending_per_username
    ON signup_requests (lower(username)) WHERE status = 'pending';

-- ============================================================
-- Доступ. Бэкенд ходит под владельцем таблиц и RLS не мешает ему.
-- ============================================================
-- Включаем построчную защиту без единой политики: любой другой роли строки недоступны.
-- На Supabase это закрывает таблицы от публичного Data API (ключ anon не секрет).
ALTER TABLE people          ENABLE ROW LEVEL SECURITY;
ALTER TABLE scrobbles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE signup_requests ENABLE ROW LEVEL SECURITY;

-- Дополнительно снимаем права у ролей Data API. Роли есть только на Supabase,
-- поэтому блок ничего не делает на обычном Postgres.
DO $$
DECLARE r text;
BEGIN
    FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
            EXECUTE format('REVOKE ALL ON people, scrobbles, signup_requests FROM %I', r);
        END IF;
    END LOOP;
END $$;
