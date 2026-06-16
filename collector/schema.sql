-- 중앙 저장소 스키마 (SQLite)
-- 여러 기기·여러 브라우저의 방문기록을 한곳에 모은다.

CREATE TABLE IF NOT EXISTS devices (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,          -- 기기 이름 (예: my-laptop, work-pc)
    os         TEXT,                          -- 수집 당시 OS 정보
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
);

CREATE TABLE IF NOT EXISTS visits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   INTEGER NOT NULL REFERENCES devices(id),
    browser     TEXT NOT NULL,                -- chrome / firefox / safari / edge / brave ...
    url         TEXT NOT NULL,
    domain      TEXT,                          -- 그룹/필터용 도메인
    title       TEXT,
    visit_time  INTEGER NOT NULL,             -- Unix epoch 초 (UTC)
    source      TEXT NOT NULL DEFAULT 'collector',  -- collector / takeout / manual
    inserted_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now')),

    -- 같은 기기·브라우저에서 같은 URL을 같은 시각에 방문한 기록은 한 건으로 본다.
    -- (기기가 다르면 비교 대상이므로 중복 제거하지 않는다.)
    UNIQUE (device_id, browser, url, visit_time)
);

CREATE INDEX IF NOT EXISTS idx_visits_time    ON visits(visit_time);
CREATE INDEX IF NOT EXISTS idx_visits_device  ON visits(device_id);
CREATE INDEX IF NOT EXISTS idx_visits_browser ON visits(browser);
CREATE INDEX IF NOT EXISTS idx_visits_domain  ON visits(domain);
