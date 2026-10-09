import { closeSync, openSync, readdirSync, unlinkSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type { ExtensionAPI, ExtensionContext } from '@earendil-works/pi-coding-agent';

// Reserve both names exclusively so concurrent Pi processes cannot overwrite reports.
function writeReports(cwd: string, usage: string, time: string) {
  let number = readdirSync(cwd).reduce((max, name) => {
    const match = /^agents-(\d+)-(usage|time)\.txt$/.exec(name);
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0) + 1;
  for (;; number++) {
    const files: { path: string; fd: number }[] = [];
    try {
      for (const suffix of ['usage', 'time']) {
        const path = join(cwd, `agents-${number}-${suffix}.txt`);
        files.push({ path, fd: openSync(path, 'wx', 0o600) });
      }
    } catch (error) {
      for (const file of files) {
        closeSync(file.fd);
        unlinkSync(file.path);
      }
      if ((error as NodeJS.ErrnoException).code === 'EEXIST') continue;
      throw error;
    }
    try {
      writeFileSync(files[0].fd, usage);
      writeFileSync(files[1].fd, time);
    } catch (error) {
      for (const file of files) unlinkSync(file.path);
      throw error;
    } finally {
      for (const file of files) closeSync(file.fd);
    }
    return;
  }
}

export default function metering(pi: ExtensionAPI) {
  let run: {
    start: bigint;
    cwd: string;
    entryIds: Set<string>;
    active: boolean;
    outcome: string;
  } | undefined;
  const start = (ctx: ExtensionContext) => ({
    start: process.hrtime.bigint(),
    cwd: ctx.cwd,
    entryIds: new Set(ctx.sessionManager.getEntries().map(entry => entry.id)),
    active: false,
    outcome: 'completed',
  });

  pi.on('input', (_event, ctx) => {
    if (!run?.active) run = start(ctx);
  });
  pi.on('before_agent_start', (_event, ctx) => {
    run ??= start(ctx);
    run.active = true;
  });
  pi.on('agent_before_settle', event => {
    if (run?.active) run.outcome = event.outcome;
  });
  pi.on('agent_settled', (_event, ctx) => {
    if (!run?.active) return;
    const completed = run;
    run = undefined;
    const seconds = Number(process.hrtime.bigint() - completed.start) / 1e9;
    let uncached = 0, cached = 0, output = 0;
    for (const entry of ctx.sessionManager.getEntries()) {
      if (completed.entryIds.has(entry.id)) continue;
      const usage = entry.type === 'message' && entry.message.role === 'assistant'
        ? entry.message.usage
        : entry.type === 'compaction' || entry.type === 'usage' ? entry.usage : undefined;
      if (!usage) continue;
      uncached += (usage.input ?? 0) + (usage.cacheWrite ?? 0);
      cached += usage.cacheRead ?? 0;
      output += usage.output ?? 0;
    }
    const outcome = `outcome: ${completed.outcome}\n`;
    try {
      writeReports(completed.cwd,
        `${outcome}input_tokens_total: ${uncached + cached}\ninput_tokens_cached: ${cached}\ninput_tokens_uncached: ${uncached}\noutput_tokens: ${output}\n`,
        `${outcome}elapsed_seconds: ${seconds.toFixed(6)}\n`);
    } catch (error) {
      const message = `Pi metering could not write reports: ${error}`;
      console.error(message);
      ctx.ui.notify(message, 'error');
    }
  });
}
