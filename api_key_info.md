# API key management: reference for LLM agents

This repository runs the Pi coding agent in Docker for the Text-to-MfG benchmark.
The API keys it uses (DeepSeek, Brave Search, and a mentor's NASA keys) must never
reach GitHub or the Pi logs that get saved. This file describes how that is
enforced and what you must and must not do.

## Rules for agents

- Never print, echo, `cat`, log, or paste a key value. That includes chat replies,
  commit messages, file contents, and shell commands such as `echo $DEEPSEEK_API_KEY`.
- Never write a real key into any file inside this repository. Docs and examples use
  placeholders such as `DEEPSEEK_API_KEY=<your key>`.
- Never read `~/.config/text-to-mfg/keys.env` to display it. If you must check it,
  mask the values: `sed 's/=.*/=<hidden>/' ~/.config/text-to-mfg/keys.env`.
- Never bypass the pre-commit hook (`git commit --no-verify`) unless the user confirms
  that the blocked content is a false positive.
- Never `docker commit` or `docker push` a container started with keys, and never run
  Pi's `/login` inside the container.
- If a user pastes a key into a chat, store it only in the key file (below), then tell
  them it was exposed in the transcript and should be rotated.
- Do not push to GitHub unless the user explicitly asks.

## Where keys live

- **Host key file:** `~/.config/text-to-mfg/keys.env`, outside the repository. The
  directory is mode `700` and the file is mode `600`, with one `NAME=value` per line
  and no quotes needed:
  - `DEEPSEEK_API_KEY`: model requests.
  - `BRAVE_SEARCH_API_KEY`: the `web_search` tool.
  - Any other key, such as a NASA key, works automatically if its variable name
    contains `KEY`, `TOKEN`, or `SECRET` (case-insensitive).
- **Into the container:** only at runtime, through the file:
  ```sh
  docker run -it --env-file ~/.config/text-to-mfg/keys.env text-to-mfg:latest
  ```
  Never use `-e NAME=value`, because it lands in shell history. Keys are not baked into
  the image.

## Protection layers

### 1. Shell environment stripping: `Docker contents/offline-shell.c`

Both the agent's `bash` tool and the user's interactive `!` commands run through
`/usr/local/bin/pi-offline-shell`. Before it execs `/bin/bash`, it:

- removes every environment variable whose name contains `KEY`, `TOKEN`, or `SECRET`;
- applies a seccomp filter that blocks `socket`, `connect`, `io_uring_setup`, `ptrace`,
  `process_vm_readv`, `process_vm_writev`, and `pidfd_getfd`. Shell commands therefore
  have no network access and cannot read Pi's memory.

Pi's own Node process keeps the keys, which it needs for model and search requests.
CAD/FEA settings (`PYTHONPATH`, `PI_MODAL_FEA_STATE`, `PI_COMPUTE_LOG`) are untouched.

**Known gap:** a shell running as the same user can still read the parent processes'
startup environment through `/proc/<pid>/environ`, and `docker run` puts the keys there.
Layer 2 handles this.

### 2. Log redaction: `Docker contents/redact.ts`

A Pi extension, loaded by `Docker contents/pi-launcher.sh`, that replaces the value of
every `KEY`/`TOKEN`/`SECRET` variable (values of 8 or more characters) with
`[REDACTED]` before Pi shows or saves it:

- `tool_result` hook: covers every tool, including `read` on `/proc/self/environ`.
- `message_end` hook: covers user prompts and model replies, such as a provider
  error that repeats a key.
- `redactingOperations()`: wraps the shell operations in `Docker contents/web-search.ts`
  so streamed `bash` and `!` output is redacted one line at a time, which means a key
  split across output chunks is still caught. Interactive `!` output is recorded
  outside `message_end`, so this wrapper is the only thing that covers it.

**Limit:** it matches the exact text only. A key that has been deliberately
transformed (base64, reversed, split into pieces) is not caught. Stopping that would
require running the shell as a separate Linux user.

### 3. Git protection: `.githooks/pre-commit` and `.gitignore`

- The hook blocks a commit if the staged additions contain:
  - the value of any exported `*KEY*`/`*TOKEN*`/`*SECRET*` variable in the committer's shell;
  - any value in `~/.config/text-to-mfg/keys.env`;
  - a DeepSeek-style key (`sk-` followed by 32 hex characters);
  - a long literal assigned to a key/token/secret name.

  Fake `canary-*` values, used by the redaction test, are exempt from the last two
  checks, so always use that prefix for fake keys.
- It must be enabled once per clone: `git config core.hooksPath .githooks`. It is
  enabled in the original author's clone.
- `.gitignore` excludes `*.env`, `.env`, and `auth.json`.
- Recommended: GitHub secret scanning push protection, enabled in the repository settings.

### 4. Documentation

`Docker contents/README.md` (credentials section) and the root `README.md` (the
"Keeping API keys out of git" section) give the human-facing version of these
instructions.

## Verifying it works

Build the image from the repository root, then run the fake-key test:

```sh
docker build -f "Docker contents/Dockerfile" -t text-to-mfg:latest .
docker run --rm -e PI_NETWORK_IMAGE_TEST=1 -e DEEPSEEK_API_KEY=canary-deepseek-0123456789 -e BRAVE_SEARCH_API_KEY=canary-brave-0123456789 -e NASA_API_KEY=canary-nasa-0123456789 -v "$PWD/Docker contents/redact.test.mjs:/opt/pi/redact.test.mjs:ro" -w /opt/pi text-to-mfg:latest node --test redact.test.mjs
```

`Docker contents/redact.test.mjs` checks that:

- `env` in both the agent shell and the `!` shell shows no key variables, while
  `PYTHONPATH` and gmsh still work;
- a full agent session that dumps `/proc/$PPID/environ` and `/proc/1/environ`, reads
  `/proc/self/environ`, has the model repeat the keys, and runs a `!` command produces a
  saved session `.jsonl` containing `[REDACTED]` and none of the canary values.

Last verified on 2026-10-16: all tests passed. Running `node --test` locally on the
author's Mac hangs on importing the Pi package, which is an unrelated existing
problem, so run the tests in the image.

After changing any of these files, rebuild the image and recreate the containers.

## If a key leaks

1. Rotate it immediately in the provider's dashboard and delete the old key.
2. Put the new key in `~/.config/text-to-mfg/keys.env`. Do not paste it into a chat.
3. If it was committed, rewriting git history is not enough once it has been pushed.
   Rotation is the fix.
4. Check saved Pi logs and `L1 Runs/` with
   `grep -rF "<first 10 characters of the old key>"`.

## What this does not cover

- Anyone with Docker access on the host can see the keys with `docker inspect <container>`.
- Keys pasted into an LLM chat are stored in that tool's transcripts (for Claude Code,
  `~/.claude/projects/`) and sent to its provider.
- Keys whose variable names lack `KEY`, `TOKEN`, or `SECRET` are neither stripped nor redacted.
