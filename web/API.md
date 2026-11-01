# Jalboot Support API

The exact REST and streaming contract between the web app in this folder and the FastAPI backend.
The TypeScript source of truth is `src/api/types.ts`. Jalboot is a fictional company and all data is invented.

## Conventions

| Topic | Rule |
| --- | --- |
| Base path | `/api/v1`. The web app reads it from `VITE_API_BASE`. |
| Bodies | JSON, UTF-8, camelCase keys. |
| Language | The client sends `Accept-Language: en` or `ar`. Every human-readable string in a response uses that language, including `label`, `summary` and `detail`. |
| Times | ISO 8601 in UTC, for example `2026-11-02T15:40:00Z`. The UI shows them in Asia/Qatar. |
| Money | Numbers in QAR, 2 decimals at most. Field names end in `Qar`. |
| IDs | Opaque strings. |
| CORS | When the site and API are on different origins, allow the headers `Authorization`, `Content-Type`, `Accept-Language`, `Last-Event-ID`, `X-CSRF-Token`. Desk routes also need `Access-Control-Allow-Credentials: true` and an exact origin, never `*`. Outside production, `http://localhost:5173` and `http://127.0.0.1:5173` are allowed by default. |

### Authentication

| Area | How | Comes from |
| --- | --- | --- |
| Customer | `Authorization: Bearer <conversation token>`, held in memory | `POST /conversations` |
| Desk | HttpOnly cookie `jalboot_desk`, plus `X-CSRF-Token` on every POST | `POST /desk/session` |
| Policy | None | Public |

Desk rules:

- The cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` outside local development. Page scripts cannot read it, so a
  script injected into the page cannot steal the session.
- Every desk request uses `credentials: 'include'` and sends no `Authorization` header. This includes `GET /desk/events`.
- `csrfToken` is kept in memory only, never in `localStorage` or `sessionStorage`. A page refresh gets a new copy from
  `GET /desk/me`.
- `SameSite=Lax` means the cookie is only sent when the page and the API are on the same site. Serve the live desk from
  the same site as the API. The GitHub Pages demo does not call the API, so it is not affected.

### Errors

Every non-2xx response uses this envelope. FastAPI's default `{ "detail": "..." }` is tolerated, but the
screens only show precise messages when `error.code` is present, so install an exception handler.

```json
{
  "error": {
    "code": "invalid_code",
    "message": "That code is not right.",
    "retryable": true,
    "attemptsLeft": 3,
    "retryAfterSeconds": null
  }
}
```

`message` is shown to the user, so write it in the request language. `attemptsLeft` and `retryAfterSeconds`
are optional and only used by the identity endpoints.

| Status | `code` | When |
| --- | --- | --- |
| 400 | `invalid_code` | Wrong identity code. Include `attemptsLeft`. |
| 401 | `unauthorized` | Missing or expired token, or an unknown conversation. A customer route answers the same for both, so that conversation ids cannot be probed. The desk shows its sign-in form. |
| 401 | `invalid_credentials` | Wrong email or password. The answer is the same whether or not the email has an account. |
| 403 | `approval_limit_exceeded` | The signed-in person may not decide this refund. |
| 403 | `origin_not_allowed` | A state-changing request came from an origin that is not on the list. |
| 403 | `csrf_failed` | `X-CSRF-Token` is missing or stale. The client calls `GET /desk/me` for a fresh token and retries once. |
| 404 | `not_found` | Unknown refund, or a conversation looked up from the desk. |
| 409 | `turn_in_progress` | A reply is already streaming in this conversation. |
| 409 | `duplicate_message` | Same `clientMessageId` as a turn that already completed. |
| 409 | `refund_already_decided` | Stale `version`, or the refund is no longer pending. |
| 409 | `amount_exceeds_paid` | Approving would pay more than is left on the order. It is checked again at decision time. |
| 409 | `conversation_closed` | A message was sent to a closed conversation. |
| 410 | `code_expired` | Identity code expired. |
| 422 | `invalid_phone` | The phone number is not valid. |
| 422 | `validation_error` | Any other malformed body. |
| 429 | `too_many_attempts` | Identity locked or rate limited. Include `retryAfterSeconds` and a `Retry-After` header. |
| 500 | `internal_error` | Set `retryable: true`. |

### Server-Sent Events

Both stream types use standard SSE. The `event:` line carries the event name and `data:` carries one JSON
object on one line.

```text
event: tool.start
data: {"toolCallId":"t1","tool":"track_order","label":"Checking your order"}

```

- Headers: `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- The client reads streams with `fetch`, not `EventSource`, so POST and `Authorization` both work.
- Send a comment line (`: ping`) every 15 seconds on long-lived streams.
- Unknown event names are ignored, so new events can be added without breaking the page.
- On `GET` streams, send `id:` on every event and resume after the `Last-Event-ID` request header. The client
  reconnects with exponential backoff from 1 to 30 seconds and stops on any 4xx.

## Policy

### `GET /policy`

Public. Called once at startup. It holds only what a customer may be told. Approval limits are internal (REF-05,
ESC-03), because someone who knows a limit can size a claim to fit under it, so they are never in this response. If
the call fails or a value is null, the UI leaves that sentence out.

```json
{
  "policyVersion": "2026.11",
  "currency": "QAR",
  "assistant": "mock",
  "refund": {
    "cardBusinessDays": 7,
    "creditMinutes": 15
  }
}
```

Serve these from `knowledge/rules.json`:

| Field | `rules.json` path |
| --- | --- |
| `policyVersion` | `meta.policy_version` |
| `currency` | `meta.currency` |
| `refund.cardBusinessDays` | `refunds.timing.card_business_days` |
| `refund.creditMinutes` | `refunds.timing.credit_minutes` |

`assistant` is `mock` when replies come from fixed rules and `live` when they come from a real model. It does not come
from `rules.json`. `POST /conversations` sends it too. While it is `mock`, the page shows a "Mock replies" label.

## Customer chat

### `POST /conversations`

No auth. Request `{ "locale": "ar" }`. Response 201:

```json
{
  "id": "cv_8f2a",
  "token": "opaque-conversation-token",
  "locale": "ar",
  "createdAt": "2026-11-02T15:40:00Z",
  "verified": false,
  "assistant": "mock"
}
```

### `POST /conversations/{id}/messages`

Sends a customer message and streams the reply as SSE.

```json
{ "clientMessageId": "c0a1", "text": "Where is my order?", "locale": "en" }
```

`text` is 2000 characters at most, and `clientMessageId` is 64.

`clientMessageId` makes the call safe to repeat. A repeat with the same ID must not store a second customer
message. It re-runs the turn if the earlier run ended in `identity.required` or `error`, and returns 409
`duplicate_message` if the earlier run completed.

`text` is plain text in both directions. Never send HTML or Markdown. The UI splits paragraphs on a blank line.

#### Stream events

| Event | Data | Meaning |
| --- | --- | --- |
| `message.start` | `{ "messageId": "m1" }` | Opens the reply. Always first. A held turn that runs again repeats its `messageId`, and the UI opens a new reply. |
| `tool.start` | `{ "toolCallId": "t1", "tool": "track_order", "label": "Checking your order" }` | A tool began. **The UI shows `label` as written**, and has no list of tools. `label` is required, in plain language, in the conversation language. |
| `tool.end` | `{ "toolCallId": "t1", "status": "ok", "label": "Checked your order" }` | `status` is `ok` or `error`. `label` is optional and replaces the shown text. Use it for the past tense. A refusal by the rules or the identity check is `ok`: `error` means a call was broken. |
| `text.delta` | `{ "delta": "Your order " }` | Append to the reply. |
| `order.card` | `{ "order": Order }` | Show an order card. A repeat with the same `order.id` replaces it. |
| `citation` | `{ "citation": Citation }` | Registers source `[n]`. Send it **before** the text that uses the marker. |
| `refund.update` | `{ "refund": RefundSummary }` | Show or update a refund card. |
| `handoff.update` | `{ "handoff": Handoff }` | Handoff state changed. |
| `identity.required` | `{ "reason": "order_tools" }` | Order tools were refused because the conversation is not verified. See [Identity](#identity). |
| `message.end` | `{ "finish": "complete" }` | Closes the reply. Always last. `finish` is `complete`, `handoff`, `identity_required` or `forwarded`. |
| `error` | `{ "error": { "code": "...", "message": "...", "retryable": true } }` | Ends the reply as failed. Replaces `message.end`. |

Reply text refers to sources with markers such as `[1]`, ASCII digits in square brackets. A marker with no matching
`citation` event is shown as plain text.

When a person has taken over, the backend stores the message, forwards it to them, and answers with `message.start`
and `message.end` with `finish: "forwarded"`. There is no text, so the UI shows no reply.

#### Example

```text
event: message.start
data: {"messageId":"m1"}

event: tool.start
data: {"toolCallId":"t1","tool":"track_order","label":"Checking your order"}

event: tool.end
data: {"toolCallId":"t1","status":"ok","label":"Checked your order"}

event: order.card
data: {"order":{"id":"JB-48213","vertical":"food","status":"on_the_way","store":"Saffron Door Kitchen","area":"West Bay","placedAt":"2026-11-02T15:02:00Z","etaAt":"2026-11-02T15:54:00Z","deliveredAt":null,"rider":"Salim","items":[{"name":"Chicken machboos","qty":1,"priceQar":42}],"feesQar":6.62,"totalQar":60.62}}

event: citation
data: {"citation":{"n":1,"sourceId":"late-or-missing-orders","title":"Late or missing orders","section":"Late credits","excerpt":"...","updatedAt":"2026-11-01T00:00:00Z"}}

event: text.delta
data: {"delta":"Your order is on the way [1]."}

event: message.end
data: {"finish":"complete"}

```

### Identity

The backend refuses order tools until the conversation is verified. **The phone number and the code travel only
through the two endpoints below. They must never enter chat text, the conversation history or the model's context.**

1. A turn needs an order tool and the conversation is not verified. The backend streams `message.start`,
   `identity.required`, text such as "I need to confirm it is you first", and `message.end` with
   `finish: "identity_required"`. It keeps the customer message.
2. The UI locks the chat box, so nothing typed during the check can reach the model, and shows a phone form.
3. The UI calls `verify/start`, then shows a code form.
4. The UI calls `verify/confirm`.
5. On success the UI repeats `POST /messages` with **the same `clientMessageId` and text**. The backend runs the
   held turn without storing the message twice.

The customer can cancel the check. The chat box unlocks and general questions still work. Asking about an order
again sends `identity.required` again.

#### `POST /conversations/{id}/verify/start`

```json
{ "phone": "+97433001234" }
```

`phone` is E.164. The UI converts Arabic-Indic digits and adds `+974` to an 8 digit local number.

Response 200:

```json
{
  "status": "code_sent",
  "maskedPhone": "+974 •••• 1234",
  "expiresInSeconds": 300,
  "resendInSeconds": 30,
  "simulatedCode": "482913"
}
```

- Return the same response whether or not the number has an account, so the endpoint cannot be used to find customers.
- `simulatedCode` is present **only in simulated mode**, and the UI shows it in a panel labelled as a simulated SMS.
  Omit it or send `null` whenever a real SMS is sent. The UI never fills the code in by itself.
- Calling this endpoint again sends a new code and cancels the old one. The UI offers this after `resendInSeconds`.
- Errors: 422 `invalid_phone`, 429 `too_many_attempts`.

#### `POST /conversations/{id}/verify/confirm`

```json
{ "code": "482913" }
```

The UI converts Arabic-Indic digits to ASCII before sending. Response 200:

```json
{ "verified": true, "customerName": "Sara" }
```

Errors:

| Status | `code` | UI |
| --- | --- | --- |
| 400 | `invalid_code` | Shows `message` and `attemptsLeft`, stays on the code form. |
| 410 | `code_expired` | Shows `message`, offers a new code. |
| 429 | `too_many_attempts` | Shows `message`, ends the check. Lockout follows `account.otp` in `rules.json`. |

Write `identity.verified` or `identity.failed` to the audit log, without the phone number or the code.

### `POST /conversations/{id}/handoff`

No body. Response 200 is a `Handoff`. Automated replies stop. Later changes arrive as `handoff.update` on the
events stream. No verification is needed to reach a person. A summary never stops a handoff, however long the
customer's first message was. If the handoff really fails the answer is 500 `internal_error` with `retryable: true`,
never a 200, so the page can say so and let the customer ask again.

### `GET /conversations/{id}/events`

Long-lived SSE stream, open while the conversation is on screen.

| Event | Data |
| --- | --- |
| `handoff.update` | `{ "handoff": Handoff }` |
| `refund.update` | `{ "refund": RefundSummary }` |
| `agent.message` | `{ "messageId": "a1", "agentName": "Noor", "text": "Hello", "at": "..." }` |
| `conversation.closed` | `{ "at": "..." }` |

`refund.update` must reach the customer when a person decides. On approval send `note: null`, because an approval
note is for the audit log only. On rejection `note` is the reason the customer sees.

## Support desk

Everything here except `POST /desk/session` needs the `jalboot_desk` cookie. A 401 shows the sign-in form.

### `POST /desk/session`

No CSRF token, since there is no session yet. Request `{ "email": "...", "password": "..." }`. Response 200 sets the
`jalboot_desk` cookie. The body holds no session token:

```json
{ "csrfToken": "opaque-csrf-token", "agent": DeskAgent }
```

### `GET /desk/me`

Restores the session after a refresh. Response 200:

```json
{ "agent": DeskAgent, "csrfToken": "opaque-csrf-token" }
```

A 401 means signed out, and the UI shows the sign-in form.

### `POST /desk/logout`

Needs `X-CSRF-Token`. No body. Ends the session and clears the cookie. Response 204.

### `GET /desk/policy`

Needs a desk session. The only place the UI gets approval limits.

```json
{
  "refund": {
    "automatedLimitQar": 50,
    "newAccountAutomatedLimitQar": 25,
    "agentLimitQar": 300,
    "supervisorLimitQar": 1500
  }
}
```

### `GET /desk/summary`

Response 200 is a `DeskSummary`.

### `GET /desk/conversations`

Response 200 is `{ "conversations": LiveConversation[] }`. The UI does the sorting.

### `GET /desk/conversations/{id}`

Response 200 is a `ConversationDetail`.

### `POST /desk/conversations/{id}/claim`

No body. Response 200 is the `LiveConversation` with `state: "agent"`. Stops automated replies and sends the
customer `handoff.update` with `status: "joined"`.

### `POST /desk/conversations/{id}/reply`

Request `{ "text": "..." }`, 2000 characters at most. Response 204. Sends the customer `agent.message`.

### `POST /desk/conversations/{id}/close`

No body. Response 200 is the `LiveConversation` with `state: "closed"`. Sends the customer `conversation.closed`.
A later customer message gets 409 `conversation_closed`.

### `GET /desk/refunds`

Response 200 is `{ "refunds": Refund[] }`: everything pending, plus decisions from the current shift. The UI splits
and sorts them.

### `POST /desk/refunds/{id}/decision`

```json
{ "action": "approve", "note": "", "version": 3 }
```

`action` is `approve` or `reject`. `note` is at most 1000 characters. It is required on `reject`, at least 8 characters, and the customer sees it. `version` is the value the
agent was looking at. Response 200 is the updated `Refund`. Errors: 409 `refund_already_decided`,
403 `approval_limit_exceeded`.

### `GET /desk/audit?filter=all&cursor=`

`filter` is `all`, `bot`, `agent` or `guardrail`. Newest first, 10 or more per page.

```json
{ "entries": [AuditEntry], "nextCursor": "opaque-or-null" }
```

`bot` excludes `guardrail.blocked`. `guardrail` returns only `guardrail.blocked`.

### `GET /desk/metrics/top-issues?windowDays=7`

`windowDays` is 7, 14 or 30. Response 200 is `{ "issues": TopIssue[] }`.

### `GET /desk/metrics/quality?windowDays=7`

Response 200 is a `QualityReport`.

### `GET /desk/events`

Long-lived SSE stream. It authenticates with the cookie, read through `fetch` with `credentials: 'include'` and no
`Authorization` header.

| Event | Data |
| --- | --- |
| `conversation.updated` | `{ "conversation": LiveConversation }` |
| `conversation.message` | `{ "conversationId": "...", "entry": TranscriptEntry }` |
| `refund.created` | `{ "refund": Refund }` |
| `refund.updated` | `{ "refund": Refund }` |
| `audit.appended` | `{ "entry": AuditEntry }` |
| `summary.updated` | `{ "summary": DeskSummary }` |

## Objects

### Order

```ts
{
  id: string;
  vertical: 'food' | 'grocery' | 'pharmacy' | 'parcel';
  status: string;            // A value from general.order_status_paths or general.terminal_statuses
  store: string;
  area: string;
  placedAt: string;
  etaAt: string | null;
  deliveredAt: string | null;
  rider: string | null;
  items: { name: string; qty: number; priceQar: number; flag?: 'missing' | 'wrong' }[];
  feesQar: number;           // Delivery, service and any other fees together
  totalQar: number;
}
```

The card shows four steps: placed, getting ready, on the way, delivered.

| Step | Statuses |
| --- | --- |
| Placed | `placed`, `accepted` |
| Getting ready | `preparing`, `ready`, `picking`, `packed`, `driver_assigned` |
| On the way | `picked_up`, `on_the_way` |
| Delivered | `delivered` |
| Stopped, no step shown | `cancelled`, `failed_customer` |

### Citation

```ts
{ n: number; sourceId: string; title: string; section: string; excerpt: string; updatedAt: string }
```

### RefundSummary

```ts
{
  id: string;
  orderId: string;
  amountQar: number;
  status: 'auto_approved' | 'pending' | 'approved' | 'rejected';
  decidedBy: string | null;
  note: string | null;
}
```

### Handoff

```ts
{
  status: 'requested' | 'queued' | 'joined' | 'closed';
  agentName: string | null;
  etaMinutes: number | null;
  position: number | null;
}
```

### DeskAgent

```ts
{ id: string; name: string; role: 'agent' | 'supervisor' | 'finance_lead' }
```

### DeskSummary

```ts
{ live: number; waiting: number; refundsPending: number; resolvedToday: number }
```

### LiveConversation

```ts
{
  id: string;
  customer: string;
  locale: 'en' | 'ar';
  state: 'bot' | 'waiting' | 'agent' | 'closed';
  priority: 'normal' | 'high';
  verified: boolean;
  summary: string;
  orderId: string | null;
  agentName: string | null;
  startedAt: string;
  updatedAt: string;
  waitingSince: string | null;   // Set while state is 'waiting'
}
```

### ConversationDetail

`LiveConversation` plus `transcript: TranscriptEntry[]`.

### TranscriptEntry

```ts
{
  id: string;
  at: string;
  author: 'customer' | 'bot' | 'agent' | 'system';
  name: string | null;
  text: string;          // Stays in the customer's language. Never holds a phone number or a code.
  tools: string[];       // Plain-language labels, as in tool.start or tool.end
  sources: string[];     // Titles of cited sources
}
```

### Refund

`RefundSummary` plus:

```ts
{
  conversationId: string;
  customer: string;
  store: string;
  reason: 'missing_item' | 'wrong_item' | 'late' | 'quality';
  summary: string;
  requestedAt: string;
  decidedAt: string | null;
  recommendation: 'approve' | 'review' | 'reject';
  evidence: { label: string; value: string }[];
  policy: { title: string; section: string };
  risks: string[];
  version: number;
  canDecide: boolean;              // Can the signed-in person decide this one?
  requiredRole: 'agent' | 'supervisor' | 'finance_lead';
}
```

The backend works out `canDecide` and `requiredRole` from `refunds.approval_limits_qar`, including the finance lead
tier above the supervisor limit and the rule that an amount exactly at a limit stays at that level. The UI never
compares amounts against a limit. It disables the buttons when `canDecide` is false and names `requiredRole`.

### AuditEntry

```ts
{
  id: string;
  at: string;
  actorKind: 'bot' | 'agent' | 'system';
  actorName: string;
  action: string;
  target: string;
  detail: string;
}
```

The UI has labels for `tool.called`, `refund.auto_approved`, `refund.proposed`, `refund.approved`,
`refund.rejected`, `handoff.requested`, `handoff.joined`, `agent.replied`, `guardrail.blocked`,
`identity.verified` and `identity.failed`. Any other value is shown as sent. `detail` must never hold a phone
number or a code.

### TopIssue

```ts
{ id: string; label: string; count: number; changePct: number }
```

`changePct` compares against the window before this one. Sort order does not matter.

### QualityReport

```ts
{
  windowDays: 7 | 14 | 30;
  hero: QualityTile;
  tiles: QualityTile[];
  series: { date: string; value: number }[];   // One per day for hero, oldest first
}
```

### QualityTile

```ts
{
  id: string;
  label: string;
  value: number;
  unit: 'percent' | 'seconds' | 'score';
  delta: number;            // Against the previous window, in the tile's unit
  higherIsBetter: boolean;
  trend: number[];          // Oldest first
}
```

## Tool labels

The UI has no tool list, so a new tool works as soon as it sends a `label`. These are suggested labels for the current
tools. Send the language of the conversation.

| Tool | `tool.start` en | `tool.start` ar | `tool.end` en | `tool.end` ar |
| --- | --- | --- | --- | --- |
| `get_customer_profile` | Opening your account | جارٍ فتح حسابك | Opened your account | تم فتح حسابك |
| `track_order` | Checking your order | جارٍ التحقق من طلبك | Checked your order | تم التحقق من طلبك |
| `get_order_details` | Reading your order details | جارٍ قراءة تفاصيل طلبك | Read your order details | تمت قراءة تفاصيل طلبك |
| `issue_refund` | Working on your refund | جارٍ تجهيز الاسترداد | Worked on your refund | تم تجهيز الاسترداد |
| `issue_credit` | Adding credit to your account | جارٍ إضافة رصيد إلى حسابك | Added credit to your account | تمت إضافة الرصيد إلى حسابك |
| `apply_promo` | Checking your promo code | جارٍ التحقق من الرمز الترويجي | Checked your promo code | تم التحقق من الرمز الترويجي |
| `change_address` | Updating your address | جارٍ تحديث عنوانك | Updated your address | تم تحديث عنوانك |
| `cancel_order` | Cancelling your order | جارٍ إلغاء طلبك | Cancelled your order | تم إلغاء طلبك |
| `create_ticket` | Opening a ticket with the team | جارٍ فتح تذكرة مع الفريق | Opened a ticket with the team | تم فتح تذكرة مع الفريق |
| `handoff_to_human` | Finding a person to help | جارٍ البحث عن موظف لمساعدتك | Asked a person to help | تم طلب موظف لمساعدتك |
| `search_knowledge` | Reading the help pages | جارٍ قراءة صفحات المساعدة | Read the help pages | تمت قراءة صفحات المساعدة |
| `explain_delay` | Finding out what caused the delay | جارٍ معرفة سبب التأخير | Found out what caused the delay | تمت معرفة سبب التأخير |

If a tool fails, send `status: "error"` and a `label` that says so in plain language.

## Scripted examples

The GitHub Pages build plays scripted examples with no backend. They are written by hand, not captured from real
conversations, and the page labels each one "Scripted example". An example is a list of `{ waitMs, event }` steps,
using the events above plus `customer.message` and these three, which exist only in examples. They hold no phone
number and no code.

| Event | Data |
| --- | --- |
| `identity.code_sent` | `{ "maskedPhone": "+974 •••• 1234" }` |
| `identity.verified` | `{}` |
| `identity.cancelled` | `{}` |
