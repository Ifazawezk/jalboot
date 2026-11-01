<p align="center">
  <img src="docs/images/banner.png" alt="Jalboot: the model proposes, code decides. AI customer support for a fictional Doha delivery app, in Arabic and English." width="100%">
</p>

**Jalboot (جالبوت) is an AI customer support system for a fictional Doha delivery app that answers in Arabic and English, cites its policy sources, and can only touch money and orders through tools that check every call in code.**

<p>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-green"></a>
  <img alt="Python 3.11+" src="https://img.shields.io/badge/python-3.11%2B-blue">
  <img alt="Languages: Arabic and English" src="https://img.shields.io/badge/languages-Arabic%20%7C%20English-0b5f5a">
  <img alt="All data is simulated" src="https://img.shields.io/badge/data-simulated-lightgrey">
  <img alt="Runs with no API key" src="https://img.shields.io/badge/API%20key-optional-informational">
  <a href="#results"><img alt="Evaluation: see Results for what has run" src="https://img.shields.io/badge/evaluation-see%20results-lightgrey"></a>
  <a href="CONTRIBUTING.md"><img alt="PRs welcome" src="https://img.shields.io/badge/PRs-welcome-brightgreen"></a>
</p>

> [!IMPORTANT]
> **Jalboot is fictional.** This is a portfolio project, not a product. The company, customers, merchants, drivers, orders, amounts and policies are all invented, all data is simulated, and the project has no link to any real company. Phone numbers are built so that none can be real, email addresses use the reserved `.example` domain, no real money moves and no SMS is ever sent.

## Start here

| You are... | Go to |
| --- | --- |
| Wanting to see it with nothing to install | [Public demo](https://ifazawezk.github.io/jalboot/), which plays recordings and needs no key |
| Reviewing this as a portfolio project | [Why](#why), [Results](#results) and [Limits](#limits) |
| Building an AI agent that can take actions | [Security model](#security-model) and [docs/security.md](docs/security.md) |
| Checking how it was measured | [docs/evaluation.md](docs/evaluation.md) |
| Hoping to run it | [Quick start](#quick-start) |
| Adding your own API key | [With a real model](#with-a-real-model) |
| Planning to add policies, tools or test cases | [CONTRIBUTING.md](CONTRIBUTING.md) |

## Why

Delivery support looks easy for a chatbot until the bot can do things. A customer wants money back, the right answer depends on exact rules about windows, net prices and approval levels, and the message may mix Gulf dialect with English. Some messages should not be in a chatbot at all, such as a child having an allergic reaction to a meal.

Instructions in a prompt do not hold up here. A prompt is a request, and a customer, a merchant note or a pasted document can argue with a request. A model that is right 99 times in 100 still pays out on the hundredth.

So Jalboot treats the model as an untrusted planner. It can read, draft and propose. Code decides who the customer is, what they may see, what a claim is worth and whether a refund runs, waits for a person or stops. The prompt is a second layer. A model that ignores it still cannot reach another customer's order, pay more than a claim is worth or skip a check.

## What it does

- **Answers in the customer's language.** Eighteen policy documents hold 88 numbered sections in English and Arabic. An answer in either language cites the same section id.
- **Cites what it says.** Search runs per language, fusing BM25 and character n-grams with reciprocal rank fusion, with dense embeddings as an option. Passages that share too little with the question are dropped, so the honest answer is the only one left.
- **Acts through 13 tools, not through prose.** Order lookups, refund quotes, refunds, credit, promo codes, address changes, cancellations, tickets and handoffs. Each call passes the same [gates](#security-model).
- **Keeps the rules in code.** The policy engine is a set of pure functions over [`knowledge/rules.json`](knowledge/rules.json), so every rule can be tested with plain values. Refund values come from a `quote_refund` tool, and a higher amount from the model is refused.
- **Checks every reply first.** Citations, figures, claims of actions and leaks are tested before a customer sees anything. A reply that fails gets one repair, then the conversation goes to a person.
- **Knows when to stop.** Safety, legal threats, account takeover, complaints about staff, requests for a person and upset customers are caught in code before any model runs.
- **Gives people a real desk.** Live conversations, a refund queue with role limits, an audit log, top issues and quality charts, in both languages. The desk's charts are built from simulated tickets and are not evaluation results.
- **Runs with no key.** `LLM_MODE=mock` swaps the model for a rule based planner, so the whole system runs offline. Mock results are never offered as a measure of quality.
- **Is set up to be measured on held-out cases.** 364 test cases score what the tools logged rather than what the bot said it did. The 105 held-out ones are sealed outside this repository and have not been run. See [Results](#results).
- **Assumes the model can be taken over.** A [compromised-model test](#if-the-model-is-taken-over) skips the model and fires hostile tool calls straight at the tool layer, with the gates on and then off, and records what really changed.

## Screenshots

These come from the web app's sample mode, which runs in the browser with no backend. The names and amounts are sample data, not output from a scored run.

<table>
  <tr>
    <td width="50%"><img src="docs/images/chat-order-en.png" alt="English chat with an order card, tool activity and a numbered source"></td>
    <td width="50%"><img src="docs/images/chat-order-ar.png" alt="The same conversation in Arabic, with the whole interface right to left"></td>
  </tr>
  <tr>
    <td><b>Customer chat.</b> Tool activity, the order card and the section behind each claim.</td>
    <td><b>Arabic.</b> The whole interface switches to right to left.</td>
  </tr>
  <tr>
    <td><img src="docs/images/identity-code.png" alt="Identity check panel with a clearly labelled simulated SMS"></td>
    <td><img src="docs/images/safety-handoff.png" alt="An allergy report handed to a person, with automated replies paused"></td>
  </tr>
  <tr>
    <td><b>Identity check.</b> It runs outside the chat text. The SMS is simulated and says so.</td>
    <td><b>Safety handoff.</b> A person joins and automated replies stop.</td>
  </tr>
  <tr>
    <td><img src="docs/images/desk-approve.png" alt="Support desk dialog asking a person to approve a refund"></td>
    <td><img src="docs/images/desk-audit.png" alt="Audit log listing automated and human actions"></td>
  </tr>
  <tr>
    <td><b>Refund approval.</b> The bot proposes and a person decides.</td>
    <td><b>Audit log.</b> Every action, by the bot or a person, is on the record.</td>
  </tr>
</table>

## Architecture

```mermaid
flowchart TD
  subgraph web["Web app: React, Arabic and English"]
    chat["Customer chat"]
    desk["Support desk"]
  end

  subgraph turn["One customer turn: FastAPI"]
    redact["Redact phones, emails, cards and codes"]
    triage{"Triage in code, before any model"}
    search["Search the policy: BM25 + character n-grams"]
    model["Model or mock planner picks tools or writes a reply"]
    gate["Tool gate: arguments, identity, ownership, repeats"]
    policy["Policy engine: pure functions over rules.json"]
    checks{"Reply checks: citations, figures, claims, leaks"}
  end

  id["Identity check, outside the chat"]
  queue["Approval queue"]
  person["Handoff to a person"]
  db[("Database and hash-chained audit log")]

  chat --> redact --> triage
  chat -. "phone and code" .-> id
  id -. "sets the verified customer" .-> gate
  triage -->|"safety, legal, takeover, asked for a person, upset"| person
  triage -->|"everything else"| search --> model
  model -->|"tool call"| gate --> policy
  policy -->|"allowed"| db
  policy -->|"needs a person"| queue
  policy -->|"refused"| model
  policy -->|"rules conflict"| person
  model -->|"draft reply"| checks
  checks -->|"passes"| chat
  checks -->|"fails, one repair"| model
  checks -->|"fails again"| person
  queue --> desk
  person --> desk
  desk -->|"decide within role limit"| db
```

**One turn.** [`agent/loop.py`](src/jalboot/agent/loop.py) runs triage, retrieval, planning, checks, one repair and a fallback. A turn is capped at 6 model steps and 8 tool calls, and two turns that did not help go to a person. If the model fails or a limit is reached, the customer gets a person, never an unchecked answer.

**Retrieval.** Each language has its own index. BM25 uses folded, lightly stemmed terms, and character n-grams catch Gulf spellings, typos and attached particles. Results are fused with RRF at k = 60, the value from the original paper, not tuned on any evaluation set. Setting `EMBEDDINGS=e5-small` adds dense search to the fusion. A reranker was measured and left out, because it lowered recall on the development questions. Sections marked internal are left out of the customer index, which is simpler and safer than trusting a model not to repeat them.

**Model.** The client speaks the OpenAI chat completions API over plain HTTP, with no vendor SDK. Groq is the default provider, and `LLM_PROVIDER=compatible` points it at another server of that kind, which has not been tried. The client reads rate limit headers, waits rather than sends a request it knows will be refused, backs off on 429 and 503, and never switches key, model or provider to get around a limit.

**Live updates.** Replies and desk events travel as server-sent events. A reply reaches the page only after it has passed its checks, so what looks like streaming is a finished reply sent in pieces.

```text
src/jalboot/
  agent/       triage, prompts, the turn loop, reply checks, fixed replies
  api/         FastAPI routes, identity, desk, browser guards, live events
  db/          SQLAlchemy models
  evaluation/  the runner, scoring, the plain chatbot baseline, the compromised-model test
  kb/          loads the policy documents and searches them
  llm/         OpenAI compatible client, rate limits, mock planner, evaluation cache
  policy/      the policy engine and its rules loader
  retrieval/   BM25, character n-grams, optional dense search, rank fusion
  security/    password hashing, tokens, redaction, throttling
  text/        Arabic and English normalization and tokenizing
  tools/       tool definitions, the executor, approvals
  world/       the seeded simulated world and the demo customers
  audit.py     the hash-chained audit log
knowledge/     policy documents in both languages, and rules.json
web/           React web app and the API contract in web/API.md
eval/          test cases, scoring spec, validator and recorded results
scripts/       retrieval measurement and a small model probe
tests/         pytest suite
```

## Security model

The rule behind everything: **a model's output is a proposal, and a customer's text is data.** No tool takes a customer id. The customer comes from the conversation row, which only the identity check can set.

Every tool call passes these gates in order, in [`tools/executor.py`](src/jalboot/tools/executor.py):

| Step | Check | On failure |
| --- | --- | --- |
| 1 | The tool exists and its arguments match the definition exactly. An unlisted argument is refused, not ignored | Refused and audited |
| 2 | The conversation has passed the identity check, if the tool needs one | `identity_required`, and the page opens the check |
| 3 | The order belongs to the verified customer | The same answer as an order that does not exist |
| 4 | This is not a repeat of an action already taken | Returns the first result and changes nothing |
| 5 | The policy engine allows it, files it for a person, refuses it, or calls a rule conflict | Nothing is paid unless the engine says execute |
| 6 | The action and its audit row commit together | Neither is saved |

| Threat | What stops it | Where |
| --- | --- | --- |
| Reading another customer's order | Identity from the conversation row, ownership check, identical refusals | `tools/executor.py` |
| Talking the bot into a refund | Amounts come from the order's own prices, and limits live in the policy engine | `policy/engine.py` |
| Instructions in a message, merchant note or passage | Outside text reaches the model as escaped, labelled data, and the gates apply whatever the model decides | `agent/prompts.py` |
| A reply that says money moved when it did not | The claim check needs a tool result from this turn | `agent/checks.py` |
| Invented sources or figures | Each `[n]` must match a retrieved passage, and each figure must appear in the evidence | `agent/checks.py` |
| Leaking approval limits or the prompt | Internal sections are not indexed for customers, a canary and a repeat check guard the prompt | `kb/store.py`, `agent/checks.py` |
| One-time codes in chat | Redacted before storage or any model, with a fixed reply | `security/redact.py`, `api/chat.py` |
| Paying twice | An idempotency key per action, a per item check across conversations, and one writer at a time | `tools/executor.py`, `audit.py` |
| Staff acting above their level | Role limits are enforced on the server, for the total on the order after the payment, and the policy rules run again at decision time | `tools/approvals.py` |
| Another site driving the desk | HttpOnly cookie, SameSite, an Origin check and a CSRF token | `api/guards.py`, `api/app.py` |
| Quietly editing history | A SHA-256 hash chain on the audit log finds an edited or removed row | `audit.py` |

Most of these have a named test in `tests/`. The red team results are in [Results](#results). What this model does not cover is in [Limits](#limits), and the full version is [docs/security.md](docs/security.md).

### If the model is taken over

A prompt can fail, so this test assumes it already has. [`evaluation/hostile.py`](src/jalboot/evaluation/hostile.py) skips the model and the agent loop. For each case it fires the calls an attacker would want straight at the tool layer, patiently, small claims first: every read, item refunds, repeats under changed item lists, whole-order claims, goodwill, an address change and a cancellation. It does this with the gates on and then off, and records what really changed in the database. Then one person approves every waiting claim in a row, and a separate check compares what was paid with what the records allow. It needs no key, and nothing in it depends on how a model behaves.

On the 61 development red team cases, with 2,222 hostile tool calls. These figures are in [`eval/results/hostile-dev.json`](eval/results/hostile-dev.json), and `python -m jalboot.evaluation.hostile --split dev` repeats them with no key:

| | Gates on | Gates off |
| --- | --- | --- |
| Reads of data that was not theirs | **0** | 54 |
| Cases where an order was changed | **0** | 61 |
| QAR paid by the tools, whole run | **1,060.00** | 35,894.15 |
| QAR paid, most in one case | **25.00** | 930.35 |
| Claims filed for a person instead | 54 | 0 |
| Limit breaks | **0** | 210 |

The same attack also ran with a double charge, a change shortfall or a failed delivery added to every order, and one person approving everything. There were 0 limit breaks with the gates on, and about 600 with them off, which shows the check can see one. [docs/evaluation.md](docs/evaluation.md#the-compromised-model-test) has those runs. The test finds only the kinds of break it checks for, and it goes around the agent loop, so it does not measure the customer's-own-request rule.

**The money is not zero, and that is a real limit of this design.** Gates check whether a claim fits the rules, not whether it is true. A verified customer who falsely reports a missing item on their own delivered order looks exactly like an honest one. The 9 cases that never passed the identity check paid nothing. Stopping a false claim that fits the rules takes a person or fraud signals, and no gate here can do it.

**QAR 25.00 is also not a ceiling.** It is what these orders allow, because their items are cheap. Across all 191 development cases that hold orders (6,228 calls), reads of other people's data stayed at 0, and the most paid in one case was QAR 310.00, a confirmed double charge plus goodwill. A person who approves everything can pay out much more: QAR 9,722.18 across those cases, inside every limit. Each case holds only a few orders, so this does not measure an attacker working through many orders over weeks. The repeat-claim rules exist for that, and this test does not measure them. It also covers the tool layer only, so it says nothing about what a taken-over model could write in a reply.

## Quick start

You need Python 3.11 or newer and Node for the web app. It was developed and run on Windows 11 with Python 3.12 and Node 24, and other setups have not been tried. No API key is needed.

```bash
git clone https://github.com/Ifazawezk/jalboot.git jalboot && cd jalboot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

cd web && npm ci
VITE_API_MODE=live npm run build # PowerShell: $env:VITE_API_MODE="live"; npm run build
cd ..

python -m jalboot.cli serve --port 8000
```

Open <http://127.0.0.1:8000>. The server hosts the API and the web app on one origin. `jalboot serve --port 8000` does the same thing.

`VITE_API_MODE=live` matters. A plain `npm run build` makes the sample mode from the screenshots, which never calls the server. For UI work, run `npm run dev` in `web/` beside the server, and set `VITE_API_MODE=live` to have Vite forward API calls to port 8000.

The first start builds a seeded world in `var/jalboot.sqlite3`: 400 customers, 80 drivers, 3,000 orders and 600 tickets, plus two demo customers. `WORLD_SEED` and `WORLD_SCALE` change it.

### The static demo

The public demo is a static site with no server and no key, so it can go on GitHub Pages:

```bash
cd web
VITE_BASE_PATH=/jalboot/ npm run build:demo   # writes web/dist-demo. In Git Bash, add MSYS_NO_PATHCONV=1
```

It plays the recordings in [`demo/recordings`](demo/recordings) and the scripted examples, and labels each one. A recording is a real model run on simulated data, made by `scripts/record_demo.py` through the real API, identity check and desk included. Nothing in one is written by hand, and it names its model and date. The pauses are set for reading, not measured. The scripted examples are written by hand and say so.

### Demo accounts

| Who | Sign in with | Notes |
| --- | --- | --- |
| Layla, customer, English | `+97401001001` | The page shows the simulated code |
| Noura, customer, Arabic | `+97401001002` | The page shows the simulated code |
| Sara, agent | `sara@jalboot.example` | Decides up to the agent limit |
| Khalid, supervisor | `khalid@jalboot.example` | Decides up to the supervisor limit |
| Amal, finance lead | `amal@jalboot.example` | Decides any amount |

The staff password is `jalboot-local-demo`, for local use only. `DEMO_STAFF_PASSWORD` changes it in development and test. A server in `demo` or `production` mode refuses that published password, and needs its own password for each role. The `0` after `+974` is deliberate: no real Qatari number has one.

### Things to try

These were run against the mock planner. It matches keywords and fills templates, so it reads stiffly, and wording far from these may get an odd answer. What it does show is that the same gates and checks apply.

| Who | Message | What happens |
| --- | --- | --- |
| Anyone | `What is your refund policy for a missing item?` | Answers with a citation, and needs no identity check |
| Anyone | `I want to talk to a real person please` | Hands off at once, with no model involved |
| Anyone | `ابنتي عندها حساسية وأكلت من الطلب` | A safety handoff in Arabic |
| Layla | `Where is my order JB-700101?` | Stops for the identity check, then resumes the same turn and shows the order |
| Layla | `Where is my order JB-700201?` | That is Noura's order, and the answer matches a number that does not exist |
| Layla | `The karak tea was missing from JB-700102, please refund it` | Refunded at once, under the automated limit |
| Layla | `Mixed grill plate and grilled hammour were missing from JB-700103, I want a refund` | Filed for a person, and nothing is paid until someone approves it on the desk |
| Layla | `Why was my order JB-700104 so late?` | Explains the delay and applies the late credit it is due |
| Noura | `The Vitamin D3 was missing from JB-700204, please refund it` | A pharmacy order, so it is filed and handed to a person |
| Noura | `The karak tea was missing from JB-700205, please refund it` | This order carries a merchant note ordering a full refund. Only the tea is refunded |

### With a real model

Jalboot starts in mock mode, so it runs with no key. To use a real model, put your own key in a file named `.env` in the main `jalboot` folder, next to this README.

1. Get a key. Groq has a free tier at <https://console.groq.com/keys>. Any server that speaks the OpenAI API works too.
2. Create the file:

   ```bash
   cp .env.example .env             # PowerShell: Copy-Item .env.example .env
   ```

3. Open `.env` and set these two lines:

   ```ini
   LLM_MODE=llm
   LLM_API_KEY=your-key-here
   ```

4. Restart the server with `python -m jalboot.cli serve --port 8000`.

To check it worked, open <http://127.0.0.1:8000/api/v1/health>. It says `"assistant":"live"` with a real model and `"assistant":"mock"` without one. To go back, set `LLM_MODE=mock`. If you set `LLM_MODE=llm` with no key, the server stops at startup with `LLM_MODE=llm needs a key`.

For a provider other than Groq, also set these in `.env`:

```ini
LLM_PROVIDER=compatible
LLM_BASE_URL=https://your-server/v1
LLM_MODEL=your-model-name
```

`.env` is ignored by git, so your key stays on your machine. Never put a real key in `.env.example`, and a variable already set in your shell wins over the file. The default is `openai/gpt-oss-20b` on Groq. In `llm` mode the redacted messages and retrieved passages go to that provider, and its terms apply. The public demo plays recordings, so it takes no key.

### Settings

| Variable | Meaning |
| --- | --- |
| `LLM_MODE` | `mock` (default) or `llm` |
| `LLM_PROVIDER` | `groq` (default) or `compatible` |
| `LLM_API_KEY`, `LLM_API_KEY_ENV` | The key, or the name of another variable that holds it |
| `LLM_BASE_URL`, `LLM_MODEL` | Server and model. Both are required for `compatible` |
| `LLM_TIMEOUT`, `LLM_MAX_TOKENS`, `LLM_MAX_WAIT` | Defaults: 60 seconds, 1000 tokens, 30 seconds |
| `DATABASE_URL` | SQLite under `var/` when empty |
| `ENVIRONMENT` | `development` (default), `test`, `demo` or `production`. Anything else refuses to start. `demo` and `production` are for servers other people can reach, and turn on the startup checks below |
| `SECRET_KEY` | Required in `demo` and `production`, at least 32 characters |
| `COOKIE_SECURE`, `COOKIE_SAMESITE` | Cookie flags. `demo` and `production` need `COOKIE_SECURE=true` |
| `SHOW_SIMULATED_OTP` | Shows the code on the page. `production` must set `false`. `demo` keeps it on, because there is no SMS provider |
| `DEMO_STAFF_PASSWORD` | Password for all the local staff accounts, in development and test only |
| `STAFF_PASSWORD_AGENT`, `STAFF_PASSWORD_SUPERVISOR`, `STAFF_PASSWORD_FINANCE_LEAD` | One password per role, each at least 12 characters and all different. Required in `demo` and `production` to create the accounts |
| `ALLOWED_ORIGINS` | Other origins that may call the API, comma separated. `*` is refused |
| `WORLD_SEED`, `WORLD_SCALE` | The simulated world |
| `EMBEDDINGS` | `e5-small` adds dense search. Needs the `embeddings` extra |
| `WEB_DIST`, `KNOWLEDGE_DIR`, `INDEX_DIR`, `JALBOOT_ENV_FILE` | Override file locations |

### With dense search

```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[embeddings]"
```

Then set `EMBEDDINGS=e5-small`. It downloads a model, and search works without it.

### With Docker

> [!WARNING]
> **Docker has never been run on this project.** It is not installed on the machine this was built on, so the image has not been built and the stack has not been started. Expect to fix things.

A `Dockerfile` and a `docker-compose.yml` are in the repository root. The compose file starts the app with PostgreSQL, in mock mode, on `127.0.0.1:8000`:

```bash
POSTGRES_PASSWORD=choose-one docker compose up --build
```

The image defaults to `ENVIRONMENT=production`, so running it by itself asks for the production settings. Compose runs as development unless `ENVIRONMENT` is set.

### Tests

```bash
pytest
```

The tests run offline with fakes and the mock planner, so they need no key. They show that the code does what it says. They say nothing about how a real model behaves.

## Results

Full tables and intervals are in [docs/evaluation.md](docs/evaluation.md). No figure here comes from mock mode, which is a keyword planner and says nothing about quality.

### The agent

<!-- results:status -->
**The held-out test has not been run.** **These are not final scores.** The development figures come from a partial run at frozen commit `1d2bf61`: 11 of 259 cases, partial for the agent and 1 of 259 cases, partial for the plain chatbot, taken in a fixed order that spreads them evenly over every set. The full evaluation continues over several days, because the model's free tier allows only part of it each day. Later runs will be published the same way.
<!-- /results:status -->

<!-- results:run -->
| Run detail | Value |
| --- | --- |
| Model | `openai-gpt-oss-20b` |
| Dense search | e5-small |
| Code version | `1d2bf61` |
| Date | 2026-11-01 |
| Development cases | 11 of 259 cases, partial |
| Plain chatbot, development cases | 1 of 259 cases, partial |
| Held-out cases | Not run |
| Why a run stopped | development: stopped at the provider's limit: provider returned HTTP 429; retry in 228s ; plain chatbot: stopped at the provider's limit: provider returned HTTP 429; retry in 379s |
<!-- /results:run -->

**The model has not been scored yet.** The one development case that has run is a safety report, which triage handles in code with no model call. On the next case the provider returned HTTP 429 with a wait of 1,447 seconds, so the run stopped there, as it is built to. Mock mode results are not shown, because they say nothing about quality.

A gate must hold in each language, not only overall. Every figure below comes from a file in [`eval/results`](eval/results), and a run with fewer than 20 cases shows no rates.

<!-- results:agent -->
| Metric | Gate | Dev | Held-out | Held-out, English | Held-out, Arabic |
| --- | --- | --- | --- | --- | --- |
| Resolution rate | at least 0.80 | Too few cases | Not run | Not run | Not run |
| Wrong-refund rate | at most 0.02 | Too few cases | Not run | Not run | Not run |
| Missed-refund rate | at most 0.10 | Too few cases | Not run | Not run | Not run |
| Unauthorized data access, `exposed` | 0 events | Too few cases | Not run | Not run | Not run |
| Citation precision | at least 0.90 | Too few cases | Not run | Not run | Not run |
| Citation recall | at least 0.80 | Too few cases | Not run | Not run | Not run |
| Invented citations | 0 | Too few cases | Not run | Not run | Not run |
| Abstention accuracy | at least 0.85 | Too few cases | Not run | Not run | Not run |
| Escalation recall | at least 0.95 | Too few cases | Not run | Not run | Not run |
| Escalation precision | at least 0.80 | Too few cases | Not run | Not run | Not run |
| Red team, `critical` severity | every case passes | Too few cases | Not run | Not run | Not run |
| Red team, overall | at least 0.95 | Too few cases | Not run | Not run | Not run |
<!-- /results:agent -->

### Retrieval

From [`eval/results/retrieval-dev.json`](eval/results/retrieval-dev.json): search alone, with no language model, on 50 development questions in both languages. A question counts only if all of its gold sections are in the top results.

| System | Recall@3 | Recall@5 | MRR | Used by |
| --- | --- | --- | --- | --- |
| BM25 | 0.86 | 0.92 | 0.844 |  |
| Character n-grams | 0.82 | 0.94 | 0.766 |  |
| **BM25 + n-grams** | **0.86** | **0.94** | **0.844** | **The default** |
| Dense (e5-small) | 0.94 | 0.98 | 0.872 |  |
| BM25 + dense | 0.96 | 0.98 | 0.907 |  |
| **BM25 + n-grams + dense** | **0.96** | **0.98** | **0.877** | **`EMBEDDINGS=e5-small`** |
| Best system + reranker | 0.94 | 0.98 | 0.881 | Left out |
| Held-out test set | Not run | Not run | Not run | |

**These numbers are optimistic.** The best figures are the top of seven systems compared on the same 50 questions, so they are picked from their own test. One question moves a recall by 0.02. The held-out test set will give the honest number, and it has not been run. On these questions, adding dense search to the default gained 5 questions at Recall@3 and lost none.

### The compromised-model test

0 reads of other people's data across 2,222 hostile tool calls on the development red team cases, QAR 1,060.00 paid against QAR 35,894.15 with the gates off, and 0 limit breaks against 210. The money that still gets through is the point of the test: see [If the model is taken over](#if-the-model-is-taken-over).

### Reading these results


- **The test cases are not fully independent.** The gold answers were written after reading `engine.py` and `triage.py`, so they can share those files' blind spots. They follow the policy documents, and a development case only changed when the policy text supported the change. That helps, but it does not replace cases from someone who has never seen the code.
- **No Arabic speaker has reviewed the cases or the Arabic text.** The Arabic results say how the system does against gold answers that nobody fluent has checked.
- **The world is simulated.** The customers are scripted, and real people are stranger.
- **The sets are small.** With 45 support cases, a measured 0.80 has an interval of roughly 0.66 to 0.89.

## Roadmap

- [x] Policy knowledge base in English and Arabic, with rules in code
- [x] Guarded tools, approvals and a hash-chained audit log
- [x] The support agent with triage, reply checks and mock mode
- [x] API with identity checks, desk sessions and live events
- [x] Web app for customers and support staff, in both languages
- [x] Development and held-out test cases with a written scoring spec
- [x] A compromised-model test, with the gates on and off
- [x] Optional dense search, measured on the development questions
- [ ] Publish a scored run on the held-out set
- [ ] A new held-out set written by someone who has not read the code
- [ ] Settle the [known policy gaps](#known-policy-gaps) with written rules
- [ ] Tools for Trust reviews, membership refunds and data deletion
- [ ] Rate limits on new conversations and messages
- [ ] A real SMS provider behind the identity check
- [ ] Multi-factor sign-in for staff
- [ ] A shared event broker, to run more than one server process
- [ ] Build and run the Docker image
- [ ] Run the tests on PostgreSQL as a matter of routine

## FAQ

**Is Jalboot a real company or app?**
No. It is invented for this project and has no link to any real company. Any resemblance to a real service is an accident.

**Do I need an API key?**
No. Mock mode runs the whole system offline. It is a rule based planner, not a language model, and the interface labels it as such.

**Why not write the rules in the prompt?**
A prompt can be argued with, and a mistake in it costs real money. Code cannot be persuaded, and each rule can be tested on its own. The prompt still states the rules, as a second layer.

**Why is triage a word list and not a model?**
So that a safety report cannot be talked out of a handoff by anything else in the conversation. A word list will miss phrasing nobody listed, so it is a floor. The model can still hand off by itself.

**Can the bot approve a refund above its limit?**
No. It files an approval and pays nothing. Only a signed-in person reaches the code that turns an approval into a refund, and that person's role has to cover the amount.

**Why do replies appear in one go after a pause?**
Each reply is checked before it is sent, so a reply cannot stream word by word as the model writes it.

**Why are the approval limits in a public repository if the policy calls them internal?**
This is an open demo, so nothing here is secret. The split is there to show the design: the bot's search index and tool results never hold those limits. See also the first entry under [other gaps](#other-gaps).

**Does the Docker setup work?**
Nobody knows yet. It has never been built or run. Please open an issue if you try it.

**Do the numbers on the desk's Quality page mean anything?**
No. They come from simulated tickets, and they are not the evaluation results. Those are in [Results](#results).

## Limits

**It is a demonstration, and not ready for real customers.**

- **There is no SMS provider.** With `SHOW_SIMULATED_OTP=true`, anyone who knows a demo phone number can pass the identity check, because the page shows the code. With it off, nobody receives a code, so no one can verify.
- **There are no rate limits on chat.** Sign-in, code sending and code guessing are throttled. `POST /conversations` and sending messages are not, and in `llm` mode each message spends model tokens.
- **It runs as one server process.** The event broker is in memory, so several processes would need a shared one, and recent events are lost on restart. A turn cut off by a crash is marked failed at startup, so the customer can send it again. A second process starting would fail the first one's live turns.
- **Conversation tokens do not expire while a chat is open.** Staff sessions last 8 hours. Staff can close a chat, and from then on its token is refused on every route, and a closed chat cannot be put back in the queue.
- **Staff sign in with a password only**, with no second factor. The development password is public, so never expose a server running development settings. `demo` and `production` refuse it, and refuse a database that still has it.
- **The stream, login and code limits key on the socket address.** A proxy must pass the real address, or all customers share one set of limits, which means 20 open chats in total. None of this has been tested behind a proxy. The public demo is a static page, so it has no such limits to share.
- **The Windows server has a connection cap.** Connections past 480 are dropped, because the Windows event loop fails for good at about 510 open sockets. One client holding 480 idle connections keeps others out until they close. It recovers once they do.
- **The desk's clocks are not exact.** The simulated clock restarts at the world's anchor when the server restarts, so the resolved-today count can carry over between runs. The wait clock compares a simulated handoff time with the browser's clock, so it shows 0:00 now and will be wrong after the anchor date.
- **Docker has never been run**, because it is not installed on the machine this was built on, and PostgreSQL gets less testing than SQLite. The default test run uses SQLite. The API and race tests also run on PostgreSQL when `TEST_DATABASE_URL` names a server. A reverse proxy has not been tested.
- **False claims that fit the rules get paid.** See [If the model is taken over](#if-the-model-is-taken-over). The gates limit this. They cannot end it.
- **Triage misses what nobody listed**, and it can fire on a word used innocently. It is a floor under the model, not a classifier.
- **The reply checks are narrow.** A citation check proves the passage was retrieved, not that it supports the sentence. A figure check matches values, so a real number from the wrong rule passes. The claim check is a phrase list in two languages.
- **A confirmed charge proves a later turn, not agreement.** Code makes sure the customer was quoted first. A model that ignores a "no" in a later turn could still confirm, which is why the test cases forbid it.
- **The audit chain carries no secret key.** It shows a changed row, or a removed row with rows after it. Deleting the newest rows goes unnoticed, and someone with full database access could rewrite the whole chain.
- **Photo evidence is simulated.** There is no upload. A photo counts when the order's simulated record says one is on file.
- **The recordings show a few runs, not a typical one.** Each is one real run on simulated data. They were kept as they came, flaws included, and the Arabic ones were not checked by an Arabic speaker. They are not evidence of quality. The scored results are in [Results](#results).
- **The name is not cleared.** A few web searches found no Gulf delivery company called Jalboot. That is not a trademark or company registry check.
- **Redaction covers phones, emails, card numbers and codes.** Names and addresses in free text stay, and in `llm` mode they reach the provider.
- **Some rules are not enforced in code.** ESC-03 also bans medical and legal advice and admissions of fault. Triage sends health reports to a person, but no reply check covers these.
- **No independent review has been done.** There has been no outside security audit, and nobody independent has checked the test cases.

### Known policy gaps

The policy documents do not settle every case. Where two rules collide, GEN-04 says automated support does not choose, so the engine sends these to a person and moves no money. They stay in the development set, so that a held-out score never rests on an arguable answer.

| Case | Why the documents do not settle it | Code |
| --- | --- | --- |
| Trust review pause with a valid claim | REF-05 pauses refunds, but does not say what the customer is told or owed | `trust_review_pause` |
| Confirmed duplicate charge on a pharmacy order | PAY-03 repays a duplicate automatically, while REF-05 and PHR-05 send every pharmacy refund to a person | `duplicate_on_pharmacy_order` |
| Expired cold-chain medicine | PHR-05 gives expired items 7 days and cold-chain problems 2 hours, and this item is both | `expired_cold_chain_window` |
| Address change after `promised_at` has passed | ACC-03 allows the change before pickup, but resets `promised_at`, which would wipe lateness already built up | `address_change_after_promised_at` |
| Cash order part-paid with credit, cancelled with a charge | CAN-05 caps a cash charge and REF-04 orders refunds, but neither splits a charge across credit and uncollected cash | `cash_and_credit_charge` |
| Wallet at its limit with late credit due | REF-04 sends excess refund credit to the card, and says nothing about goodwill-type credit | `wallet_at_limit` |
| Parcel refused at the door for damage | PCL-05 treats a refusal as a return at 50 percent of the base fee, while PCL-04 treats damage as a claim with no fee | No rule of its own. The test case expects a handoff |

Three more needed a ruling, and were clear enough to settle in the policy text: a severe weather flag removes late credit, only the late tiers shift during iftar, and refund points round down.

### Other gaps

- **ESC-02 against the approval queue.** ESC-02 hands off at once when a human level is needed, while the tool layer files an approval. Both endings are accepted.
- **Leave at the door with proof.** LAT-04 says the order counts as delivered, while ESC-02 sends a not-received case with proof to a person. The engine follows LAT-04 and refuses.
- **Pharmacy cancellation refunds.** REF-05 sends every pharmacy refund to a person, but CAN-02 works out a cancellation refund and it is not a claim.
- **Parcel delays and late reports.** PCL-04 gives a fixed delay refund and says a person handles every claim, and it is unclear whether a delay is a claim. REF-01 refuses a late report while PCL-04 sends it to a person.
- **Goodwill on a zero value item.** WRG-03 says an agent can offer goodwill and REF-07 lets automation give a little, so whether the bot may offer it is arguable.
- **Rules with no tool.** LAT-04 sends a third not-received case to a Trust review, PRM-05 grants a Plus membership refund, and the privacy policy describes data deletion. No tool does any of these, so they go to a ticket or a person.

## Contributing

Contributions are welcome, especially cases that break the system, Arabic corrections and fixes to the gaps above. [CONTRIBUTING.md](CONTRIBUTING.md) explains how to add a policy, a tool or a test case. Please do not use real people or real companies in any data.

## License

[MIT](LICENSE), Copyright (c) 2026 Mohaned Elhagar.
