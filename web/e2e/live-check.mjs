// Drives the live build in Edge against a small server that follows API.md strictly, so the
// real HTTP client is proven over real sockets: streaming, the HttpOnly cookie and CSRF.
//   VITE_API_MODE=live npx vite build --outDir dist-live
//   node e2e/live-check.mjs

import { existsSync, mkdtempSync, readFileSync, rmSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import { tmpdir } from 'node:os';
import { extname, join, normalize, resolve } from 'node:path';
import puppeteer from 'puppeteer-core';

const EDGE =
  process.env.EDGE_PATH ?? 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const PORT = 4183;
const ROOT = resolve('dist-live');
const CODE = '482913';
const PHONE = '+97433001234';
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2',
};

const results = [];
function check(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` (${detail})` : ''}`);
}

const wire = { bodies: [], deskAuthHeaders: 0, csrfRejected: 0, keptTurns: new Map(), customerMessages: 0 };
const state = {
  verified: false,
  csrf: null,
  rotateCsrfOnce: true,
  refund: {
    id: 'RF-5001',
    orderId: 'JB-48213',
    amountQar: 62.5,
    status: 'pending',
    decidedBy: null,
    note: null,
    conversationId: 'cv-live',
    customer: 'Sara',
    store: 'Saffron Door Kitchen',
    reason: 'missing_item',
    summary: 'Item missing',
    requestedAt: new Date().toISOString(),
    decidedAt: null,
    recommendation: 'approve',
    evidence: [{ label: 'Order value', value: 'QAR 60.62' }],
    policy: { title: 'Refunds and credits', section: 'REF-05' },
    risks: [],
    version: 1,
    canDecide: true,
    requiredRole: 'agent',
  },
};
const AGENT = { id: 'a1', name: 'Noor', role: 'agent' };
const POLICY = {
  policyVersion: '2026.11',
  currency: 'QAR',
  refund: {
    automatedLimitQar: 50,
    newAccountAutomatedLimitQar: 25,
    agentLimitQar: 300,
    cardBusinessDays: 7,
    creditMinutes: 15,
  },
};
const ORDER = {
  id: 'JB-48213',
  vertical: 'food',
  status: 'on_the_way',
  store: 'Saffron Door Kitchen',
  area: 'West Bay',
  placedAt: new Date().toISOString(),
  etaAt: new Date(Date.now() + 840_000).toISOString(),
  deliveredAt: null,
  rider: 'Salim',
  items: [{ name: 'Chicken machboos', qty: 1, priceQar: 42 }],
  feesQar: 6.62,
  totalQar: 60.62,
};

const customerStreams = new Set();
const deskStreams = new Set();
const sleep = (ms) => new Promise((done) => setTimeout(done, ms));
const send = (res, status, body, headers = {}) => {
  res.writeHead(status, { 'Content-Type': 'application/json', ...headers });
  res.end(body === undefined ? undefined : JSON.stringify(body));
};
const fail = (res, status, code, message, extra = {}) =>
  send(res, status, { error: { code, message, retryable: false, ...extra } });
const sse = (res) =>
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'X-Accel-Buffering': 'no',
  });
const frame = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

function readBody(req) {
  return new Promise((done) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += chunk;
    });
    req.on('end', () => {
      if (raw) wire.bodies.push(`${req.url} ${raw}`);
      done(raw ? JSON.parse(raw) : {});
    });
  });
}

async function streamReply(res, turn) {
  sse(res);
  const parts = state.verified
    ? [
        frame('message.start', { messageId: `m-${Date.now()}` }),
        frame('tool.start', { toolCallId: 't1', tool: 'a_tool_the_ui_has_never_seen', label: 'Checking your order' }),
        frame('tool.end', { toolCallId: 't1', status: 'ok', label: 'Checked your order' }),
        frame('order.card', { order: ORDER }),
        frame('citation', {
          citation: { n: 1, sourceId: 's', title: 'Late or missing orders', section: 'LAT-01', excerpt: 'Text', updatedAt: '2026-11-01T00:00:00Z' },
        }),
        frame('text.delta', { delta: 'طلبك في ' }),
        frame('text.delta', { delta: 'الطريق [1].' }),
        frame('refund.update', { refund: state.refund }),
        frame('message.end', { finish: 'complete' }),
      ]
    : [
        frame('message.start', { messageId: `m-${Date.now()}` }),
        frame('text.delta', { delta: 'I need to confirm it is you first.' }),
        frame('identity.required', { reason: 'order_tools' }),
        frame('message.end', { finish: 'identity_required' }),
      ];
  // Bytes are cut at arbitrary places, in the middle of frames and of Arabic letters.
  const bytes = Buffer.from(parts.join(''));
  for (let i = 0; i < bytes.length; i += 37) {
    res.write(bytes.subarray(i, i + 37));
    await sleep(8);
  }
  res.end();
  wire.keptTurns.set(turn, state.verified ? 'done' : 'held');
}

async function customerApi(req, res, path) {
  if (path === '/policy') return send(res, 200, POLICY);
  if (path === '/conversations' && req.method === 'POST') {
    await readBody(req);
    return send(res, 201, { id: 'cv-live', token: 'tok-1', locale: 'en', createdAt: new Date().toISOString(), verified: false });
  }
  if (req.headers.authorization !== 'Bearer tok-1') return fail(res, 401, 'unauthorized', 'No token');

  if (path.endsWith('/messages')) {
    const body = await readBody(req);
    if (wire.keptTurns.get(body.clientMessageId) === 'done') {
      return fail(res, 409, 'duplicate_message', 'Already answered');
    }
    if (!wire.keptTurns.has(body.clientMessageId)) wire.customerMessages += 1;
    return streamReply(res, body.clientMessageId);
  }
  if (path.endsWith('/verify/start')) {
    const body = await readBody(req);
    if (body.phone !== PHONE) return fail(res, 422, 'invalid_phone', 'Bad number');
    return send(res, 200, {
      status: 'code_sent',
      maskedPhone: `+974 •••• ${PHONE.slice(-4)}`,
      expiresInSeconds: 300,
      resendInSeconds: 30,
      simulatedCode: CODE,
    });
  }
  if (path.endsWith('/verify/confirm')) {
    const body = await readBody(req);
    if (body.code !== CODE) return fail(res, 400, 'invalid_code', 'That code is not right.', { attemptsLeft: 4 });
    state.verified = true;
    return send(res, 200, { verified: true, customerName: 'Sara' });
  }
  if (path.endsWith('/events')) {
    sse(res);
    res.write(': ping\n\n');
    customerStreams.add(res);
    req.on('close', () => customerStreams.delete(res));
    return undefined;
  }
  return fail(res, 404, 'not_found', 'Nothing here');
}

async function deskApi(req, res, path) {
  if (req.headers.authorization) wire.deskAuthHeaders += 1;
  if (path === '/desk/session') {
    await readBody(req);
    state.csrf = 'csrf-a';
    return send(res, 200, { csrfToken: state.csrf, agent: AGENT }, {
      'Set-Cookie': 'jalboot_desk=session-1; HttpOnly; SameSite=Lax; Path=/',
    });
  }
  if (!(req.headers.cookie ?? '').includes('jalboot_desk=session-1')) {
    return fail(res, 401, 'unauthorized', 'Sign in');
  }
  if (path === '/desk/me') {
    state.csrf = state.csrf ?? 'csrf-a';
    return send(res, 200, { agent: AGENT, csrfToken: state.csrf });
  }
  if (req.method === 'POST') {
    if (state.rotateCsrfOnce && path.includes('/decision')) {
      // The server moved on, so the client's copy is stale and must be refreshed.
      state.rotateCsrfOnce = false;
      state.csrf = 'csrf-b';
    }
    if (req.headers['x-csrf-token'] !== state.csrf) {
      wire.csrfRejected += 1;
      return fail(res, 403, 'csrf_failed', 'Stale token');
    }
  }
  if (path === '/desk/logout') {
    state.csrf = null;
    return send(res, 204, undefined, { 'Set-Cookie': 'jalboot_desk=; Max-Age=0; Path=/' });
  }
  if (path === '/desk/summary') {
    const pending = state.refund.status === 'pending' ? 1 : 0;
    return send(res, 200, { live: 1, waiting: 0, refundsPending: pending, resolvedToday: 3 });
  }
  if (path === '/desk/conversations') return send(res, 200, { conversations: [] });
  if (path === '/desk/refunds') return send(res, 200, { refunds: [state.refund] });
  if (path.endsWith('/decision')) {
    const body = await readBody(req);
    if (body.version !== state.refund.version) return fail(res, 409, 'refund_already_decided', 'Decided');
    Object.assign(state.refund, {
      status: 'approved',
      decidedBy: 'Noor',
      decidedAt: new Date().toISOString(),
      version: body.version + 1,
    });
    for (const stream of customerStreams) {
      stream.write(`id: 1\n${frame('refund.update', { refund: { ...state.refund, note: null } })}`);
    }
    for (const stream of deskStreams) stream.write(`id: 1\n${frame('refund.updated', { refund: state.refund })}`);
    return send(res, 200, state.refund);
  }
  if (path === '/desk/events') {
    sse(res);
    res.write(': ping\n\n');
    deskStreams.add(res);
    req.on('close', () => deskStreams.delete(res));
    return undefined;
  }
  return fail(res, 404, 'not_found', 'Nothing here');
}

const server = createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname.startsWith('/api/v1')) {
    const path = url.pathname.slice('/api/v1'.length);
    void (path.startsWith('/desk') ? deskApi(req, res, path) : customerApi(req, res, path));
    return;
  }
  const file = join(ROOT, normalize(url.pathname === '/' ? 'index.html' : url.pathname.slice(1)));
  if (!file.startsWith(ROOT) || !existsSync(file) || statSync(file).isDirectory()) {
    res.writeHead(404).end();
    return;
  }
  res.writeHead(200, { 'Content-Type': MIME[extname(file)] ?? 'application/octet-stream' });
  res.end(readFileSync(file));
});
await new Promise((done) => server.listen(PORT, '127.0.0.1', done));

const profile = mkdtempSync(join(tmpdir(), 'jalboot-live-'));
const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  userDataDir: profile,
  args: ['--no-first-run', '--disable-extensions', '--disable-gpu', '--mute-audio'],
});

try {
  const page = await browser.newPage();
  page.setDefaultTimeout(15_000);
  await page.setViewport({ width: 1366, height: 850 });
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }]);
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));

  await page.goto(`http://127.0.0.1:${PORT}/?lang=en#/chat`);
  await page.waitForSelector('.rows button');
  check('live: no sample data banner', (await page.$('.mode')) === null);
  const rule = await page.waitForFunction(() => document.querySelector('.case .fine')?.textContent);
  check('live: limit comes from GET /policy', (await rule.jsonValue()).includes('50.00'));

  await page.click('.rows li:nth-child(1) button');
  await page.waitForSelector('.identity input[type=tel]');
  check('live: identity.required over a real stream opens the form', true);
  await page.type('.identity input[type=tel]', '33001234');
  await page.click('.identity button[type=submit]');
  await page.waitForSelector('.simsms');
  await page.type('.identity input[inputmode=numeric]', '000000');
  await page.keyboard.press('Enter');
  await page.waitForSelector('.identity .field__error');
  const attempts = await page.$eval('.identity .field__error', (el) => el.textContent);
  check('live: wrong code shows the server message and attempts left', /not right/.test(attempts) && attempts.includes('4'), attempts);
  await page.type('.identity input[inputmode=numeric]', CODE);
  await page.click('.identity button[type=submit]');

  await page.waitForSelector('.docket');
  await page.waitForSelector('.refundslip.is-pending');
  await page.waitForFunction(() => document.querySelector('.msg__body')?.textContent);
  const trail = await page.$$eval('.trail__stop', (els) => els.map((el) => el.textContent.trim()));
  check('live: a tool the UI has never seen shows its server label', trail.includes('Checked your order'), trail.join(', '));
  const reply = await page.$$eval('.msg--bot .msg__body', (els) => els[els.length - 1].textContent);
  check('live: Arabic survives bytes cut mid-letter', reply.includes('طلبك في الطريق'), reply);
  check('live: held turn reran with no second customer message', wire.customerMessages === 1, String(wire.customerMessages));
  const carriers = wire.bodies.filter((b) => b.includes(CODE) || b.includes(PHONE));
  check(
    'live: code and phone only went to the verify endpoints',
    carriers.length > 0 && carriers.every((b) => b.includes('/verify/')),
    `${carriers.length} calls`,
  );

  await page.click('.mast__nav a[href="#/desk/live"]');
  await page.waitForSelector('.signin input[type=email]');
  check('live: a 401 shows the real sign-in form', true);
  await page.type('.signin input[type=email]', 'noor@example.test');
  await page.type('.signin input[type=password]', 'password');
  await page.click('.signin button[type=submit]');
  await page.waitForSelector('.desk__head');
  check('live: signed in', true);

  const visibleCookie = await page.evaluate(() => document.cookie);
  check('live: session cookie is invisible to page scripts', !visibleCookie.includes('jalboot_desk'), visibleCookie || 'empty');
  const stored = await page.evaluate(() => JSON.stringify([{ ...localStorage }, { ...sessionStorage }]));
  check('live: no token or csrf value in browser storage', !/csrf|session-1|tok-1/.test(stored), stored);

  await page.click('.desk__nav a[href="#/desk/refunds"]');
  await page.waitForSelector('.ticket .btn--primary');
  await page.click('.ticket .btn--primary');
  await page.waitForSelector('dialog[open] button[type=submit]');
  await page.click('dialog[open] button[type=submit]');
  await page.waitForSelector('.stamp--approved');
  check('live: stale CSRF token recovered with one retry', wire.csrfRejected === 1, `${wire.csrfRejected} rejected`);
  check('live: no Authorization header on any desk call', wire.deskAuthHeaders === 0, String(wire.deskAuthHeaders));

  await page.click('.mast__nav a[href="#/chat"]');
  await page.waitForSelector('.refundslip.is-approved');
  check('live: decision reached the customer over the events stream', true);
  const body = await page.$eval('.refundslip.is-approved', (el) => el.textContent);
  check('live: refund timing comes from /policy', body.includes('7 business days'), body.slice(0, 80));

  // The chat is gone after a reload, but the desk session must survive it.
  await page.goto(`http://127.0.0.1:${PORT}/?lang=en#/desk/refunds`);
  await page.reload();
  await page.waitForSelector('.desk__head');
  check('live: a refresh restores the session from the cookie', (await page.$('.signin')) === null);

  await page.click('.desk__who .link');
  await page.waitForSelector('.signin input[type=email]');
  check('live: sign out returns to the form', true);
  await page.reload();
  await page.waitForSelector('.signin input[type=email]');
  check('live: signed out stays signed out after a refresh', true);
  check('live: no page errors', errors.length === 0, errors.slice(0, 3).join(' ; '));
} catch (error) {
  check('live: run finished', false, error.message.split('\n')[0]);
} finally {
  await browser.close();
  server.closeAllConnections();
  server.close();
  rmSync(profile, { recursive: true, force: true, maxRetries: 3 });
}

const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length} of ${results.length} checks passed`);
process.exitCode = failed.length ? 1 : 0;
