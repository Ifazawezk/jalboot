# Contributing to Jalboot

Thanks for helping. The most useful contributions are cases that break the system, corrections to the Arabic, and fixes to the [known policy gaps](README.md#known-policy-gaps).

One rule comes before the others: **Jalboot stays fictional.** Never add a real person, a real company, real customer data or a real phone number. Phone numbers use `0` straight after `+974`, which no real Qatari number has, and email addresses use the `.example` domain.

## Set up

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

The tests run offline, with fakes and the mock planner, so they need no key. They show that the code does what it says, not how a real model behaves.

For the web app:

```bash
cd web
npm ci
npm run typecheck
npm test
```

`npm run e2e` drives the built site in headless Edge. See the comment at the top of `web/e2e/run.mjs` for the builds it needs. Set `EDGE_PATH` if Edge is somewhere else.

To try a real model, copy `.env.example` to `.env` and add a key. `.env` is ignored by git. Never paste a key into an issue, a log or a commit.

**Docker has never been run on this project.** The `Dockerfile` and `docker-compose.yml` have not been built or started. If you try them, please report what happens.

## Change a policy

Policy lives in `knowledge/`: a document for each topic, and `rules.json` for every number the code uses.

1. Change the English and the Arabic together. Each section holds both, and the two must say the same thing.
2. Put any number in `rules.json` and read it through `Rules` in `src/jalboot/policy/rules.py`. Never write a limit into Python.
3. Keep decisions in `src/jalboot/policy/engine.py`, as pure functions with no database, model or clock.
4. If two rules conflict, do not pick one in code. Add the rule that settles it, or return `ESCALATE` and name the gap in the README.
5. Sections with `visibility: internal` never reach customer search. Keep it that way for limits and review triggers.
6. Add a test at the boundary. Amounts exactly on a limit are where rules go wrong.

## Add a tool

1. Define it in `src/jalboot/tools/specs.py`. Every argument is listed, because an unlisted one is refused. A tool never takes a customer id.
2. Add `_<tool name>` to `ToolExecutor` in `src/jalboot/tools/executor.py`. Use `_owned_order` for any order. Use `action_key`, `_replay` and `_remember` for anything that changes data, so a repeat changes nothing.
3. Keep rules in the policy engine, not in the handler. Do not return an internal limit to the model.
4. Add labels in both languages to `TOOL_LABELS` in `src/jalboot/api/views.py`. The web app has no tool list, so a new tool appears as soon as it sends a label.
5. Test the refused paths as well as the working one: another customer's order, no identity check, a repeat.

## Add evaluation cases

The case format is in `eval/README.md`, and the scoring rules are in `eval/SCORING.md`.

- **Add cases to `eval/dev/` only.** Do not edit, add to or read through `eval/test/`. It is held out for final scoring.
- **Write the gold answer from the policy documents, not from the code.** If the code and the policy disagree, the case is meant to fail, and that failure is a finding. Change a gold answer only if the policy changes.
- **Do not change a case because the system failed it.**
- If the gold could fairly be argued, add a `debatable` field with the reason.
- Write Arabic cases the way people type, including Gulf dialect, and not only as translations of English cases.
- Run `python eval/validate.py` before you commit. It reports the test files as missing when they are not present.

Cases from someone who has not read the backend are especially valuable, because the current ones are not fully independent of it.

To score a change:

```bash
python -m jalboot.evaluation.report --split dev --mode llm --max-requests 40
python scripts/measure_retrieval.py --split dev
```

Report numbers as they are. If a change makes them worse, keep the result and say so. Never report a score from mock mode as a measure of quality, and do not tune anything against `eval/test/`. Figures in the docs come from files in `eval/results/` or a command anyone can rerun, never from memory. Retrieval numbers from `dev` are optimistic, so say so wherever you quote them.

## Report a problem

Open an issue with the message you sent, what Jalboot did, what the policy says and the section id. If it paid wrongly, leaked data or missed a handoff, please include a test case if you can.

## Pull requests

- Keep each pull request to one change, and add tests for new behaviour.
- Run `pytest` and, for web changes, `npm run typecheck` and `npm test` in `web/`.
- Use short imperative commit messages, such as `Add a parcel delay rule`.
- Do not commit `.env`, keys, model files, databases or anything in `var/`.
- Never put a phone number or a code in a log, an audit row or chat text.
- Keep customer-facing text in both languages.
- Update `web/API.md` when the API changes.

By contributing you agree that your code is released under the [MIT license](LICENSE).
