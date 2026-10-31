// Drives the built site in real headless Edge: real clicks and keys, both languages, two widths.
//   npm run build
//   VITE_BASE_PATH=/jalboot-support/ npm run build:demo     (Git Bash: add MSYS_NO_PATHCONV=1)
//   npm run e2e
// Only one browser runs at a time, to keep memory low.

import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { extname, join, normalize, resolve } from 'node:path';
import puppeteer from 'puppeteer-core';

const EDGE =
  process.env.EDGE_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const SHOTS = resolve('screenshots');
const BASE_PATH = '/jalboot-support/';
const AXE = resolve('node_modules/axe-core/axe.min.js');
const VIEWPORTS = {
  desktop: { width: 1366, height: 850 },
  phone: { width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};
const STEP_TIMEOUT = 20_000;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
};

function serve(dir, prefix, port) {
  const server = createServer((request, response) => {
    const path = decodeURIComponent(new URL(request.url, 'http://x').pathname);
    if (!path.startsWith(prefix)) {
      response.writeHead(404).end('Outside the base path');
      return;
    }
    const relative = normalize(path.slice(prefix.length) || 'index.html');
    const file = join(dir, relative);
    if (!file.startsWith(dir) || !existsSync(file) || statSync(file).isDirectory()) {
      response.writeHead(404).end('Not found');
      return;
    }
    response.writeHead(200, { 'Content-Type': MIME[extname(file)] ?? 'application/octet-stream' });
    response.end(readFileSync(file));
  });
  return new Promise((done) => server.listen(port, '127.0.0.1', () => done(server)));
}

const results = [];

function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` (${detail})` : ''}`);
}

async function shot(page, name, fullPage = false) {
  await new Promise((done) => setTimeout(done, 120));
  await page.screenshot({ path: join(SHOTS, `${name}.png`), fullPage });
}

async function noSideScroll(page, label) {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  check(`${label}: no sideways scroll`, scrollWidth <= clientWidth, `${scrollWidth}/${clientWidth}`);
}

async function axeCheck(page, label) {
  await page.addScriptTag({ path: AXE });
  const violations = await page.evaluate(async () => {
    const report = await window.axe.run(document, {
      runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'],
    });
    return report.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.slice(0, 3).map((n) => `${n.target.join(' ')}: ${(n.any[0]?.message ?? '').slice(0, 90)}`),
    }));
  });
  check(`${label}: axe`, violations.length === 0, violations.map((v) => `${v.id} ${v.nodes.join(' | ')}`).join(' ; '));
}

async function newPage(browser, viewport, url, errors) {
  const context = await browser.createBrowserContext();
  const page = await context.newPage();
  page.setDefaultTimeout(STEP_TIMEOUT);
  await page.setViewport(viewport);
  // The machine's own theme must not decide what gets tested.
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  });
  page.on('requestfailed', (request) => {
    if (!request.failure()?.errorText.includes('ERR_ABORTED')) {
      errors.push(`failed: ${request.url()}`);
    }
  });
  await page.goto(url, { waitUntil: 'load' });
  return { page, context };
}

const streamDone = (page) =>
  page.waitForFunction(() => !document.querySelector('.send--stop') && !document.querySelector('.trail__stop.is-running'));

async function clickRow(page, selector, text) {
  const handle = await page.evaluateHandle(
    (sel, wanted) => [...document.querySelectorAll(sel)].find((el) => el.textContent.includes(wanted)),
    selector,
    text,
  );
  const element = handle.asElement();
  if (!element) throw new Error(`Nothing matching ${selector} with ${text}`);
  await element.click();
}

async function ticketButton(page, refundId, buttonSelector) {
  const handle = await page.evaluateHandle(
    (id, sel) =>
      [...document.querySelectorAll('.ticket')].find((t) => t.textContent.includes(id))?.querySelector(sel),
    refundId,
    buttonSelector,
  );
  return handle.asElement();
}

async function customerJourney(browser, lang, width, port) {
  const tag = `${lang}-${width}`;
  const errors = [];
  const { page, context } = await newPage(browser, VIEWPORTS[width], `http://127.0.0.1:${port}/?lang=${lang}#/chat`, errors);
  const rtl = lang === 'ar';
  const ask = rtl ? 'علبة التمر ناقصة من طلبي' : 'A box of dates is missing from my order';
  const phoneInput = rtl ? '٣٣٠٠١٢٣٤' : '33001234';

  try {
    await page.waitForSelector('.rows button');
    check(`${tag}: direction`, (await page.$eval('html', (h) => h.dir)) === (rtl ? 'rtl' : 'ltr'));
    await shot(page, `${tag}-01-chat-start`);
    await noSideScroll(page, `${tag} chat start`);
    await axeCheck(page, `${tag} chat start`);

    // Identity: the first order question is refused until the customer is confirmed.
    await page.click('.rows li:nth-child(1) button');
    await page.waitForSelector('.identity input[type=tel]');
    await streamDone(page);
    check(`${tag}: order question asks for identity first`, (await page.$('.docket')) === null);
    check(`${tag}: chat box locked during the check`, await page.$eval('#composer-input', (el) => el.disabled));
    check(
      `${tag}: focus moves to the phone field`,
      await page.evaluate(() => document.activeElement?.getAttribute('type') === 'tel'),
    );
    await shot(page, `${tag}-02-identity-phone`);
    await axeCheck(page, `${tag} identity phone`);

    await page.type('.identity input[type=tel]', '123');
    await page.click('.identity button[type=submit]');
    await page.waitForSelector('.identity .field__error');
    check(`${tag}: bad phone shows an error`, true);
    await page.$eval('.identity input[type=tel]', (el) => el.select());
    await page.type('.identity input[type=tel]', phoneInput);
    await page.click('.identity button[type=submit]');

    await page.waitForSelector('.simsms');
    const smsText = await page.$eval('.simsms', (el) => el.textContent);
    const code = /\d{6}/.exec(smsText)?.[0];
    check(`${tag}: simulated SMS is labelled and has a code`, /Simulated SMS|محاكاة/.test(smsText) && Boolean(code));
    check(
      `${tag}: code is not filled in for the customer`,
      (await page.$eval('.identity input[inputmode=numeric]', (el) => el.value)) === '',
    );
    await shot(page, `${tag}-03-identity-code`);
    await axeCheck(page, `${tag} identity code`);

    await page.type('.identity input[inputmode=numeric]', '000000');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.identity .field__error');
    check(`${tag}: wrong code stays on the form`, (await page.$('.identity')) !== null);
    await page.type('.identity input[inputmode=numeric]', code);
    await page.click('.identity button[type=submit]');

    // Tool activity, then the reply the refused message was waiting for.
    await page.waitForSelector('.trail__stop.is-running');
    const running = await page.$eval('.trail__stop.is-running', (el) => el.textContent.trim());
    check(`${tag}: tool activity in plain language`, /order|طلب/i.test(running), running);
    await shot(page, `${tag}-04-tool-activity`);
    await page.waitForSelector('.docket');
    await streamDone(page);
    await page.waitForSelector('.sources');

    const logText = await page.$eval('.chat__log', (el) => el.textContent);
    check(`${tag}: code and number never in the conversation`, !logText.includes(code) && !logText.includes('33001234'));
    const customerLines = await page.$$eval('.msg--customer', (els) => els.length);
    check(`${tag}: refused message is not shown twice`, customerLines === 1, String(customerLines));

    const geometry = await page.evaluate(() => {
      const message = document.querySelector('.msg--customer p').getBoundingClientRect();
      const column = document.querySelector('.chat__column').getBoundingClientRect();
      const dots = [...document.querySelectorAll('.route__dot')].map((d) => d.getBoundingClientRect().left);
      return {
        fromStart: message.left - column.left,
        fromEnd: column.right - message.right,
        first: dots[0],
        last: dots[dots.length - 1],
      };
    });
    check(
      `${tag}: customer message sits on the correct side`,
      rtl ? geometry.fromStart < geometry.fromEnd : geometry.fromEnd < geometry.fromStart,
    );
    check(`${tag}: order route runs in reading direction`, rtl ? geometry.first > geometry.last : geometry.first < geometry.last);

    await page.click('.cite');
    await page.waitForSelector('.sources details[open]');
    check(
      `${tag}: citation opens its source and takes focus`,
      await page.evaluate(() => document.activeElement?.tagName === 'SUMMARY'),
    );
    await shot(page, `${tag}-05-order-card-source`);
    await noSideScroll(page, `${tag} order card`);
    await axeCheck(page, `${tag} order card`);

    // Keyboard only: type a message and send it with Enter.
    await page.focus('#composer-input');
    await page.keyboard.type(ask);
    await page.keyboard.press('Enter');
    await page.waitForSelector('.refundslip');
    await streamDone(page);
    const refundId = await page.$eval('.refundslip .mono', (el) => el.textContent.trim());
    check(`${tag}: refund goes for approval`, (await page.$('.refundslip.is-pending')) !== null, refundId);
    await shot(page, `${tag}-06-refund-pending`);

    // Approval on the desk, by real clicks.
    await page.click('.mast__nav a[href="#/desk/live"]');
    await page.waitForSelector('.liverow');
    await shot(page, `${tag}-07-desk-live`, true);
    await noSideScroll(page, `${tag} desk live`);
    await axeCheck(page, `${tag} desk live`);

    await page.click('.desk__nav a[href="#/desk/refunds"]');
    await page.waitForSelector('.ticket');
    await shot(page, `${tag}-08-refund-queue`, true);
    await noSideScroll(page, `${tag} refund queue`);
    await axeCheck(page, `${tag} refund queue`);

    const blocked = await ticketButton(page, 'RF-2097', '.btn');
    const role = await page.evaluate(
      () => [...document.querySelectorAll('.ticket')].find((t) => t.textContent.includes('RF-2097'))?.querySelector('.ticket__role')?.textContent,
    );
    check(`${tag}: refund above the agent limit cannot be decided here`, blocked === null && Boolean(role), role);

    const approve = await ticketButton(page, refundId, '.btn--primary');
    await approve.click();
    await page.waitForSelector('dialog[open]');
    await shot(page, `${tag}-09-approve-dialog`);
    await axeCheck(page, `${tag} approve dialog`);
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => !document.querySelector('dialog[open]'));
    check(
      `${tag}: Escape closes the dialog and returns focus`,
      await page.evaluate(() => document.activeElement?.classList.contains('btn--primary')),
    );

    await (await ticketButton(page, refundId, '.btn--primary')).click();
    await page.waitForSelector('dialog[open] button[type=submit]');
    await page.click('dialog[open] button[type=submit]');
    await page.waitForSelector('.stamp--approved');
    await page.waitForFunction((id) => document.querySelector('.toast')?.textContent.includes(id), {}, refundId);
    check(
      `${tag}: focus moves to the next refund after approving`,
      await page.evaluate(() => document.activeElement?.id.startsWith('refund-')),
    );
    await shot(page, `${tag}-10-approved`, true);

    // Declining needs a reason.
    await (await ticketButton(page, 'RF-2094', '.btn:not(.btn--primary)')).click();
    await page.waitForSelector('dialog[open] textarea');
    await page.click('dialog[open] button[type=submit]');
    await page.waitForSelector('dialog[open] .field__error');
    check(`${tag}: declining without a reason is refused`, true);
    await page.type('dialog[open] textarea', rtl ? 'لم يؤكد المتجر هذا الخطأ' : 'The store could not confirm this');
    await page.click('dialog[open] button[type=submit]');
    await page.waitForSelector('.stamp--rejected');
    check(`${tag}: decline recorded`, true);

    await page.click('.desk__nav a[href="#/desk/audit"]');
    await page.waitForSelector('.ledger tbody tr');
    const ledger = await page.$eval('.ledger', (el) => el.textContent);
    check(`${tag}: approval is in the audit log`, ledger.includes(refundId), refundId);
    check(`${tag}: no code or number in the audit log`, !ledger.includes(code) && !ledger.includes('33001234'));
    await shot(page, `${tag}-11-audit`, true);
    await noSideScroll(page, `${tag} audit`);
    await axeCheck(page, `${tag} audit`);

    await page.click('.desk__nav a[href="#/desk/issues"]');
    await page.waitForSelector('.issues tbody tr');
    await shot(page, `${tag}-12-top-issues`, true);
    await noSideScroll(page, `${tag} issues`);
    await axeCheck(page, `${tag} issues`);

    await page.click('.desk__nav a[href="#/desk/quality"]');
    await page.waitForSelector('.trend svg');
    await page.click('.filters button:nth-child(2)');
    await page.waitForFunction(() => !document.querySelector('.insight.is-loading'));
    await page.$eval('.trend svg', (svg) => svg.focus());
    await page.keyboard.press(rtl ? 'ArrowRight' : 'ArrowLeft');
    await page.waitForSelector('.trend__tip');
    check(`${tag}: chart reads by keyboard`, true);
    await shot(page, `${tag}-13-quality`, true);
    await noSideScroll(page, `${tag} quality`);
    await axeCheck(page, `${tag} quality`);

    // The customer sees the decision.
    await page.click('.mast__nav a[href="#/chat"]');
    await page.waitForSelector('.refundslip.is-approved');
    check(`${tag}: customer sees the approval in chat`, true);
    await page.waitForSelector('.notice');
    await shot(page, `${tag}-14-customer-approved`);

    // Handoff.
    await page.click('.composer__foot .link');
    await page.waitForSelector('.handoff');
    await shot(page, `${tag}-15-handoff-queued`);
    await page.waitForSelector('.msg--agent');
    await page.waitForSelector('.handoff.is-joined');
    check(`${tag}: a person joins`, true);
    await shot(page, `${tag}-16-handoff-joined`);
    await axeCheck(page, `${tag} handoff`);

    // A reply from the desk reaches the chat.
    await page.click('.mast__nav a[href="#/desk/live"]');
    await page.waitForSelector('.liverow');
    await clickRow(page, '.liverow', rtl ? 'سارة' : 'Sara');
    await page.waitForSelector('.reply textarea');
    const verifiedTag = await page.$eval('.convo__facts', (el) => el.textContent);
    check(`${tag}: desk shows the identity was confirmed`, /Identity confirmed|تم تأكيد الهوية/.test(verifiedTag));
    await page.type('.reply textarea', rtl ? 'وصلني طلبك، سأتابع معك الآن.' : 'Thanks, I am looking at this now.');
    await page.click('.reply button[type=submit]');
    await page.waitForFunction(() => document.querySelectorAll('.line--agent').length > 1);
    await shot(page, `${tag}-17-desk-reply`, true);
    await page.click('.mast__nav a[href="#/chat"]');
    await page.waitForFunction(() => document.querySelectorAll('.msg--agent').length > 1);
    check(`${tag}: desk reply reaches the customer`, true);

    // Dark theme and sign-out.
    await page.click('.mast__tools .tool:last-child');
    await shot(page, `${tag}-18-dark-chat`);
    await axeCheck(page, `${tag} dark chat`);
    await page.click('.mast__nav a[href="#/desk/live"]');
    await page.waitForSelector('.liverow');
    await page.click('.desk__nav a[href="#/desk/refunds"]');
    await page.waitForSelector('.ticket');
    await shot(page, `${tag}-19-dark-queue`, true);
    await axeCheck(page, `${tag} dark queue`);
    await page.click('.desk__nav a[href="#/desk/quality"]');
    await page.waitForSelector('.trend svg');
    await shot(page, `${tag}-20-dark-quality`, true);
    await axeCheck(page, `${tag} dark quality`);

    await page.click('.desk__who .link');
    await page.waitForSelector('.signin button[type=submit]');
    check(`${tag}: sign out shows the sign-in screen`, true);
    await shot(page, `${tag}-21-signed-out`);
    await page.click('.signin button[type=submit]');
    await page.waitForSelector('.desk__head');
    check(`${tag}: signs back in`, true);
  } catch (error) {
    check(`${tag}: journey finished`, false, error.message.split('\n')[0]);
    await shot(page, `${tag}-FAILED`, true).catch(() => undefined);
  }
  check(`${tag}: no browser errors`, errors.length === 0, errors.slice(0, 4).join(' ; '));
  await context.close();
}

async function keyboardOnly(browser, port) {
  const errors = [];
  const { page, context } = await newPage(browser, VIEWPORTS.desktop, `http://127.0.0.1:${port}/?lang=en#/chat`, errors);
  try {
    await page.waitForSelector('.rows button');
    await page.keyboard.press('Tab');
    check('keyboard: first Tab reaches the skip link', await page.evaluate(() => document.activeElement?.className === 'skip'));
    await page.keyboard.press('Enter');
    check('keyboard: skip link moves to main', await page.evaluate(() => document.activeElement?.id === 'main'));
    await page.focus('.rows li:nth-child(3) button');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.sources');
    await streamDone(page);
    check('keyboard: a starter question works from the keyboard', true);
    await page.focus('.mast__nav a[href="#/desk/live"]');
    await page.keyboard.press('Enter');
    await page.waitForSelector('.liverow');
    check('keyboard: page heading takes focus after navigating', await page.evaluate(() => document.activeElement?.id === 'page-title'));
  } catch (error) {
    check('keyboard: finished', false, error.message.split('\n')[0]);
  }
  check('keyboard: no browser errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
  await context.close();
}

async function recordings(browser, lang, width, port) {
  const tag = `demo-${lang}-${width}`;
  const errors = [];
  const origin = `http://127.0.0.1:${port}`;
  const { page, context } = await newPage(browser, VIEWPORTS[width], `${origin}${BASE_PATH}?lang=${lang}#/chat`, errors);
  const offsite = [];
  page.on('request', (request) => {
    if (!request.url().startsWith(origin) && !request.url().startsWith('data:')) offsite.push(request.url());
  });
  try {
    await page.waitForSelector('.rows button');
    const banner = await page.$eval('.mode--demo', (el) => el.textContent);
    check(`${tag}: labelled as a scripted example`, /Scripted example|مثال مُعدّ مسبقًا/.test(banner));
    check(`${tag}: no chat box in a scripted example`, (await page.$('#composer-input')) === null);
    await shot(page, `${tag}-01-pick`);
    await noSideScroll(page, `${tag} pick`);
    await axeCheck(page, `${tag} pick`);

    // Missing item: watch it stream, then approve it on the desk.
    await page.click('.rows li:nth-child(2) button');
    await page.waitForSelector('.tag--rec');
    await page.waitForSelector('.identity');
    await shot(page, `${tag}-02-identity`);
    const identityText = await page.$eval('.identity', (el) => el.textContent);
    check(`${tag}: scripted identity step has no forms`, (await page.$('.identity input')) === null, identityText.slice(0, 60));
    await page.waitForSelector('.trail__stop.is-running', { timeout: 30_000 });
    await shot(page, `${tag}-03-playing`);
    await page.click('.playback__actions .btn--primary');
    await page.waitForSelector('.refundslip.is-pending');
    await page.waitForSelector('.docket');
    await shot(page, `${tag}-04-finished`);
    await axeCheck(page, `${tag} finished`);

    await page.click('.mast__nav a[href="#/desk/live"]');
    await page.waitForSelector('.liverow');
    await page.click('.desk__nav a[href="#/desk/refunds"]');
    await page.waitForSelector('.ticket');
    await (await ticketButton(page, 'RF-2091', '.btn--primary')).click();
    await page.waitForSelector('dialog[open] button[type=submit]');
    await page.click('dialog[open] button[type=submit]');
    await page.waitForSelector('.stamp--approved');
    await page.click('.mast__nav a[href="#/chat"]');
    await page.waitForSelector('.refundslip.is-approved');
    check(`${tag}: approving on the desk updates the recording`, true);

    await page.click('.playback__actions .btn:not(.btn--primary)');
    await page.waitForSelector('.rows button');
    await page.click('.rows li:nth-child(4) button');
    await page.waitForSelector('.tag--rec');
    await page.click('.playback__actions .btn--primary');
    await page.waitForSelector('.msg--agent');
    check(`${tag}: safety recording reaches a person`, true);
    await shot(page, `${tag}-05-safety`);

    check(`${tag}: nothing requested from another site`, offsite.length === 0, offsite.slice(0, 3).join(' '));
    const assets = await page.evaluate(() => performance.getEntriesByType('resource').map((r) => r.name));
    check(
      `${tag}: every asset loads under the base path`,
      assets.every((name) => name.includes(BASE_PATH)),
      `${assets.length} assets`,
    );
    const fonts = await page.evaluate(() => [...document.fonts].filter((f) => f.status === 'loaded').map((f) => f.family));
    check(`${tag}: bundled fonts loaded`, fonts.length >= 2, [...new Set(fonts)].join(', '));
  } catch (error) {
    check(`${tag}: journey finished`, false, error.message.split('\n')[0]);
    await shot(page, `${tag}-FAILED`, true).catch(() => undefined);
  }
  check(`${tag}: no browser errors`, errors.length === 0, errors.slice(0, 4).join(' ; '));
  await context.close();
}

const only = process.argv[2];
mkdirSync(SHOTS, { recursive: true });
const profile = mkdtempSync(join(tmpdir(), 'jalboot-e2e-'));
const mockServer = await serve(resolve('dist'), '/', 4181);
const demoServer = await serve(resolve('dist-demo'), BASE_PATH, 4182);
const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  userDataDir: profile,
  args: ['--no-first-run', '--disable-extensions', '--disable-gpu', '--mute-audio', '--disable-dev-shm-usage'],
});

try {
  for (const lang of ['en', 'ar']) {
    for (const width of ['desktop', 'phone']) {
      if (!only || only === `${lang}-${width}` || only === 'chat') await customerJourney(browser, lang, width, 4181);
      if (!only || only === 'demo') await recordings(browser, lang, width, 4182);
    }
  }
  if (!only || only === 'keyboard') await keyboardOnly(browser, 4181);
} finally {
  await browser.close();
  mockServer.close();
  demoServer.close();
  rmSync(profile, { recursive: true, force: true, maxRetries: 3 });
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length} of ${results.length} checks passed`);
for (const failure of failed) console.log(`  FAIL ${failure.name}: ${failure.detail}`);
process.exitCode = failed.length ? 1 : 0;
