// 백엔드(/api/*)가 없는 정적 배포(예: Vercel)에서 대시보드가 보여줄 데모 데이터 + 응답기.
// 로컬 서버가 있으면 사용되지 않는다. (브라우저/Node 양쪽에서 동작 — 테스트 가능)
(function (G) {
  const SITES = [
    ["https://news.ycombinator.com/", "Hacker News", "news.ycombinator.com"],
    ["https://github.com/", "GitHub", "github.com"],
    ["https://www.google.com/search?q=vercel", "vercel - Google 검색", "www.google.com"],
    ["https://www.youtube.com/", "YouTube", "www.youtube.com"],
    ["https://en.wikipedia.org/wiki/SQLite", "SQLite - Wikipedia", "en.wikipedia.org"],
    ["https://www.naver.com/", "NAVER", "www.naver.com"],
    ["https://stackoverflow.com/questions/42", "질문 - Stack Overflow", "stackoverflow.com"],
    ["https://news.naver.com/", "네이버 뉴스", "news.naver.com"],
    ["https://www.reddit.com/", "Reddit", "www.reddit.com"],
    ["https://chat.openai.com/", "ChatGPT", "chat.openai.com"],
    ["https://mail.google.com/", "Gmail", "mail.google.com"],
    ["https://www.notion.so/", "Notion", "www.notion.so"],
  ];
  const DEVICES = ["my-laptop", "work-pc"];
  const BROWSERS = ["chrome", "firefox", "safari", "edge"];
  const now = Math.floor(Date.now() / 1000);

  // 안정적인 데모를 위해 시드 기반 난수
  let seed = 1234567;
  const rnd = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; };

  // 기기별 전용 사이트(비교 뷰가 'A에만 / B에만'을 보여주도록)
  const EXCLUSIVE = [
    [["https://www.figma.com/", "Figma", "www.figma.com"], ["https://linear.app/", "Linear", "linear.app"]],
    [["https://jira.example.com/", "Jira", "jira.example.com"], ["https://confluence.example.com/", "Confluence", "confluence.example.com"]],
  ];
  const V = [];
  let id = 1;
  DEVICES.forEach((dev, di) => {
    const pool = SITES.concat(EXCLUSIVE[di] || []);
    for (let i = 0; i < 130; i++) {
      const s = pool[Math.floor(rnd() * pool.length)];
      V.push({
        id: id++, device: dev, device_id: di + 1,
        browser: BROWSERS[Math.floor(rnd() * BROWSERS.length)],
        url: s[0], title: s[1], domain: s[2],
        visit_time: now - Math.floor(rnd() * 14 * 86400) - Math.floor(rnd() * 86400),
      });
    }
  });

  const byCount = (m) => Object.entries(m).sort((a, b) => b[1] - a[1]);

  function filt(p) {
    const dev = p.get("device"), br = p.get("browser"), q = (p.get("q") || "").toLowerCase();
    const start = p.get("start") ? +p.get("start") : null;
    const end = p.get("end") ? +p.get("end") : null;
    return V.filter(v =>
      (!dev || String(v.device_id) === String(dev)) &&
      (!br || v.browser === br) &&
      (start === null || v.visit_time >= start) &&
      (end === null || v.visit_time < end) &&
      (!q || (v.url + " " + (v.title || "")).toLowerCase().includes(q)));
  }

  function devices() {
    const m = {};
    V.forEach(v => { (m[v.device_id] = m[v.device_id] || { id: v.device_id, name: v.device, os: "demo", visits: 0 }).visits++; });
    return Object.values(m).sort((a, b) => (a.name < b.name ? -1 : 1));
  }
  function browsers() {
    const m = {}; V.forEach(v => m[v.browser] = (m[v.browser] || 0) + 1);
    return byCount(m).map(([browser, visits]) => ({ browser, visits }));
  }
  function stats(rows) {
    const pb = {}, pd = {}, dom = {}, day = {};
    rows.forEach(v => {
      pb[v.browser] = (pb[v.browser] || 0) + 1;
      pd[v.device] = (pd[v.device] || 0) + 1;
      if (v.domain) dom[v.domain] = (dom[v.domain] || 0) + 1;
      const k = new Date(v.visit_time * 1000).toISOString().slice(0, 10);
      day[k] = (day[k] || 0) + 1;
    });
    return {
      total: rows.length,
      per_browser: byCount(pb).map(([browser, count]) => ({ browser, count })),
      per_device: byCount(pd).map(([device, count]) => ({ device, count })),
      per_day: Object.entries(day).sort().map(([d, count]) => ({ day: d, count })),
      top_domains: byCount(dom).slice(0, 15).map(([domain, count]) => ({ domain, count })),
    };
  }
  function compare(aId, bId) {
    const da = {}, db = {};
    V.forEach(v => {
      if (!v.domain) return;
      if (v.device_id === aId) da[v.domain] = (da[v.domain] || 0) + 1;
      else if (v.device_id === bId) db[v.domain] = (db[v.domain] || 0) + 1;
    });
    const A = new Set(Object.keys(da)), B = new Set(Object.keys(db));
    const pack = (arr) => arr.map(d => ({ domain: d, count_a: da[d] || 0, count_b: db[d] || 0 }));
    const both = [...A].filter(d => B.has(d)).sort((x, y) => (da[y] + db[y]) - (da[x] + db[x]));
    const onlyA = [...A].filter(d => !B.has(d)).sort((x, y) => da[y] - da[x]);
    const onlyB = [...B].filter(d => !A.has(d)).sort((x, y) => db[y] - db[x]);
    return {
      device_a: aId, device_b: bId,
      both_count: both.length, only_a_count: onlyA.length, only_b_count: onlyB.length,
      both: pack(both), only_a: pack(onlyA), only_b: pack(onlyB),
    };
  }

  G.demoAnswer = function (path) {
    const base = (G.location && G.location.origin) || "http://localhost";
    const u = new URL(path, base);
    const p = u.searchParams, pa = u.pathname;
    if (pa === "/api/health") return { ok: true, demo: true };
    if (pa === "/api/devices") return devices();
    if (pa === "/api/browsers") return browsers();
    if (pa === "/api/visits") {
      const f = filt(p).sort((a, b) => b.visit_time - a.visit_time);
      const off = +(p.get("offset") || 0), lim = +(p.get("limit") || 100);
      return { total: f.length, items: f.slice(off, off + lim) };
    }
    if (pa === "/api/stats") return stats(filt(p));
    if (pa === "/api/compare") return compare(+p.get("a"), +p.get("b"));
    return {};
  };
})(typeof window !== "undefined" ? window : globalThis);
