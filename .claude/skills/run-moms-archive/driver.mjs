#!/usr/bin/env node
// Browser harness for the "브라우저 방문기록 대시보드" web GUI.
//
// Drives the *running* dashboard with a headless Chromium (puppeteer-core +
// @sparticuz/chromium — a prebuilt Chromium that runs in restricted/headless
// containers where `apt install chromium` only yields a snap stub and the
// Playwright CDN is blocked). Loads the page, waits for real data to render,
// clicks through the three tabs, and writes a screenshot per view.
//
// The server must already be running (see SKILL.md).
//   node driver.mjs [--url http://127.0.0.1:8765] [--out /tmp/moms-archive-screens]
//
// Exits non-zero if the dashboard does not render data (e.g. API unreachable).

import { mkdirSync } from 'node:fs';
import { join } from 'node:path';
import chromium from '@sparticuz/chromium';
import puppeteer from 'puppeteer-core';

const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf(k); return i >= 0 ? argv[i + 1] : d; };
const URL = opt('--url', 'http://127.0.0.1:8765');
const OUT = opt('--out', '/tmp/moms-archive-screens');
mkdirSync(OUT, { recursive: true });

const shot = async (page, name) => {
  const p = join(OUT, name);
  await page.screenshot({ path: p });
  console.log('screenshot:', p);
  return p;
};

const browser = await puppeteer.launch({
  args: [...chromium.args, '--no-sandbox'],
  executablePath: await chromium.executablePath(),
  headless: 'shell',
});

try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1100, height: 1500 });
  const errors = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));

  console.log('navigating:', URL);
  await page.goto(URL, { waitUntil: 'networkidle2', timeout: 30000 });

  // ── 타임라인: 실제 데이터(행)가 그려졌는지 확인 ──
  await page.waitForSelector('#timeline-body tr', { timeout: 20000 });
  const conn = await page.$eval('#conn', (el) => el.textContent.trim());
  const rows = await page.$$eval('#timeline-body tr', (els) => els.length);
  const meta = await page.$eval('#timeline-meta', (el) => el.textContent.trim());
  console.log(`conn="${conn}"  timelineRows=${rows}  meta="${meta}"`);
  if (rows < 1) throw new Error('타임라인에 데이터가 없음 — API/DB 확인');
  await shot(page, '01-timeline.png');

  // ── 통계 탭 ──
  await page.click('.tabs button[data-tab="stats"]');
  await page.waitForSelector('#stat-cards .stat', { timeout: 10000 });
  const total = await page.$eval('#stat-cards .stat .n', (el) => el.textContent.trim());
  const browsers = await page.$$eval('#stat-browser .barrow', (e) => e.length);
  console.log(`stats: totalVisits=${total}  browserBars=${browsers}`);
  await shot(page, '02-stats.png');

  // ── 두 기기 비교 탭 ──
  await page.click('.tabs button[data-tab="compare"]');
  await page.waitForSelector('#cmp-run', { timeout: 10000 });
  await page.click('#cmp-run');
  await page.waitForFunction(
    () => document.querySelector('#cmp-both')?.children.length > 0,
    { timeout: 10000 },
  );
  const aTitle = await page.$eval('#cmp-a-title', (el) => el.textContent.trim());
  const bTitle = await page.$eval('#cmp-b-title', (el) => el.textContent.trim());
  console.log(`compare: "${aTitle}" / "${bTitle}"`);
  await shot(page, '03-compare.png');

  if (errors.length) console.log('console/page errors:', errors.slice(0, 5));
  console.log('DRIVER OK ✅  (screenshots in ' + OUT + ')');
} finally {
  await browser.close();
}
