# Privacy

**Status: DRAFT.** The app is not built yet. This file states the design requirements the
final code must satisfy. Re-verify every statement against the shipped code before publishing.

## What leaves the server, and where it goes
When you use an AI feature (Debug, Explain, Optimise), the app sends the following to the model
provider whose API key YOU supply:
- your SQL (with string and number literals replaced by placeholders, if you turn scrubbing on),
- any table definitions you pasted,
- any execution-plan or statistics text you pasted.

Nothing is sent to any other third party by the app. The deterministic analyzer (no AI) runs on
the server and sends nothing to a model provider.

## What the app stores
**This app stores nothing.** Query text, table definitions, pasted evidence and your API key
are held in memory for the current session only. The app does not write them to disk, a database
or logs. (Requirement for the final code; to be checked by reading it.)

## What this app cannot control
- **The model provider.** Retention, logging and training policies are the provider's, not ours.
  Read them before pasting anything sensitive.
- **The hosting platform.** Streamlit Community Cloud may log requests, IP addresses and
  metadata under its own policy.
- **Your browser and network.**

We therefore do not claim your data is "safe". We claim only what this app does.

## Literal scrubbing: what it does and does not do
Scrubbing replaces string and number literals (names, emails, ids, amounts) with placeholders
before sending, and shows you exactly what will be sent. Limits:
- **Table names, column names, schema names and aliases are NOT scrubbed.** They are often the
  sensitive part. Rename them yourself if that matters.
- **Comments are not scrubbed** unless the option to remove comments is on.
- If the scrubber cannot tokenize your SQL safely (e.g. unusual escape rules), it REFUSES to send
  rather than send a partly scrubbed query.
- It changes meaning slightly: placeholders replace values, so the model cannot reason about
  specific values. Leading/trailing `%` in LIKE patterns and the number in `TOP n` / `OFFSET` are kept.

## Pasted SQL is untrusted input
Comments and string literals can contain text aimed at the model. The app sends SQL as delimited
data, requires structured (JSON) output, re-parses every rewrite, and shows model text as plain
text only.

## For sensitive work
Run the tool locally with the deterministic analyzer only (no model call). A local-model mode
is planned (not built).
