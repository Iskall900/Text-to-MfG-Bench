import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { test } from 'node:test';
import { createJiti } from 'jiti';

const jiti = createJiti(import.meta.url);
const { default: metering } = await jiti.import(process.env.PI_METERING_IMAGE_TEST ? '/opt/pi/extensions/metering.ts' : './metering.ts');
function harness(cwd) {
  const handlers = new Map();
  const entries = [];
  const notices = [];
  const ctx = { cwd, sessionManager: { getEntries: () => entries.map((entry, index) => ({ ...entry, id: String(index) })) }, ui: { notify: (...args) => notices.push(args) } };
  metering({ on: (event, handler) => handlers.set(event, handler) });
  return { entries, notices, emit: async (event, data = {}) => handlers.get(event)?.(data, ctx) };
}
const usage = (input, cacheRead, cacheWrite, output) => ({ input, cacheRead, cacheWrite, output });
const assistant = (tokens) => ({ type: 'message', message: { role: 'assistant', usage: tokens } });

test('counts all new model usage, waits for settlement, and resets per prompt', async () => {
  const cwd = mkdtempSync(join(tmpdir(), 'pi-metering-'));
  try {
    const h = harness(cwd);
    h.entries.push(assistant(usage(999, 0, 0, 999)));
    await h.emit('input');
    await new Promise(resolve => setTimeout(resolve, 25));
    await h.emit('before_agent_start');
    h.entries.push(assistant(usage(10, 20, 3, 4)));
    await h.emit('agent_end');
    assert.deepEqual(readdirSync(cwd), []);
    await h.emit('before_agent_start'); // automatic continuation must not reset
    h.entries.push(assistant(usage(5, 6, 0, 7)), { type: 'compaction', usage: usage(2, 1, 1, 2) });
    await h.emit('agent_before_settle', { outcome: 'completed' });
    await h.emit('agent_settled');
    const report = readFileSync(join(cwd, 'agents-1-usage.txt'), 'utf8');
    assert.match(report, /input_tokens_total: 48\n/);
    assert.match(report, /input_tokens_cached: 27\n/);
    assert.match(report, /input_tokens_uncached: 21\n/);
    assert.match(report, /output_tokens: 13\n/);
    const seconds = Number(readFileSync(join(cwd, 'agents-1-time.txt'), 'utf8').match(/elapsed_seconds: ([\d.]+)/)[1]);
    assert.ok(seconds >= 0.02 && seconds < 10);
    await h.emit('agent_settled');
    assert.equal(readdirSync(cwd).length, 2);
    await h.emit('input');
    await h.emit('before_agent_start');
    h.entries.push(assistant(usage(1, 0, 0, 2)));
    await h.emit('agent_before_settle', { outcome: 'aborted' });
    await h.emit('agent_settled');
    assert.match(readFileSync(join(cwd, 'agents-2-usage.txt'), 'utf8'), /outcome: aborted\ninput_tokens_total: 1\n/);
  } finally { rmSync(cwd, { recursive: true, force: true }); }
});

test('continues numbering after restart and preserves partial existing pairs', async () => {
  const cwd = mkdtempSync(join(tmpdir(), 'pi-metering-'));
  try {
    writeFileSync(join(cwd, 'agents-8-time.txt'), 'existing');
    for (const number of [9, 10]) {
      const h = harness(cwd);
      await h.emit('before_agent_start'); // SDK callers may bypass input
      await h.emit('agent_before_settle', { outcome: 'error' });
      await h.emit('agent_settled');
      assert.match(readFileSync(join(cwd, `agents-${number}-time.txt`), 'utf8'), /outcome: error/);
    }
    assert.equal(readFileSync(join(cwd, 'agents-8-time.txt'), 'utf8'), 'existing');
  } finally { rmSync(cwd, { recursive: true, force: true }); }
});

test('reports write failures visibly without failing the agent', async () => {
  const cwd = mkdtempSync(join(tmpdir(), 'pi-metering-'));
  const h = harness(cwd);
  await h.emit('input');
  await h.emit('before_agent_start');
  rmSync(cwd, { recursive: true });
  await h.emit('agent_settled');
  assert.equal(h.notices.length, 1);
  assert.match(h.notices[0][0], /metering.*ENOENT/i);
  assert.equal(h.notices[0][1], 'error');
});

test('Pi discovers the extension automatically and meters a real agent lifecycle', async () => {
  const { cpSync, mkdirSync } = await import('node:fs');
  const { fileURLToPath } = await import('node:url');
  const { createAgentSession, DefaultResourceLoader, SessionManager, SettingsManager } = await import('@earendil-works/pi-coding-agent');
  const { fauxProvider, fauxAssistantMessage, fauxToolCall } = await import('@earendil-works/pi-ai');
  const cwd = mkdtempSync(join(tmpdir(), 'pi-metering-sdk-'));
  const agentDir = join(cwd, 'agent');
  let session;
  try {
    if (!process.env.PI_METERING_IMAGE_TEST) {
      mkdirSync(join(agentDir, 'extensions'), { recursive: true });
      cpSync(fileURLToPath(new URL('./metering.ts', import.meta.url)), join(agentDir, 'extensions', 'metering.ts'));
    }
    const faux = fauxProvider({ tokensPerSecond: 100000 });
    faux.setResponses([
      fauxAssistantMessage(fauxToolCall('read', { path: 'fixture.txt' }), { stopReason: 'toolUse' }),
      fauxAssistantMessage('finished'),
      fauxAssistantMessage('next prompt'),
    ]);
    writeFileSync(join(cwd, 'fixture.txt'), 'fixture');
    const loader = new DefaultResourceLoader({ cwd, agentDir,
      additionalExtensionPaths: process.env.PI_METERING_IMAGE_TEST ? ['/opt/pi/extensions/metering.ts'] : [],
      extensionFactories: [pi => pi.registerProvider(faux.provider)] });
    await loader.reload();
    assert.deepEqual(loader.getExtensions().errors, []);
    assert.ok(loader.getExtensions().extensions.some(extension => extension.path.endsWith('/extensions/metering.ts')));
    ({ session } = await createAgentSession({ cwd, agentDir, resourceLoader: loader, model: faux.getModel(),
      sessionManager: SessionManager.inMemory(cwd), settingsManager: SettingsManager.inMemory({ retry: { enabled: false }, compaction: { enabled: false } }) }));
    await session.prompt('Read fixture.txt, then finish.');
    await session.waitForIdle();
    assert.equal(faux.state.callCount, 2);
    const messages = session.sessionManager.getEntries().filter(entry => entry.type === 'message' && entry.message.role === 'assistant');
    const expectedOutput = messages.reduce((sum, entry) => sum + entry.message.usage.output, 0);
    assert.match(readFileSync(join(cwd, 'agents-1-usage.txt'), 'utf8'), new RegExp(`outcome: completed\\n[\\s\\S]*output_tokens: ${expectedOutput}\\n`));
    assert.ok(readFileSync(join(cwd, 'agents-1-time.txt'), 'utf8').includes('elapsed_seconds:'));
    await session.prompt('Finish again.');
    await session.waitForIdle();
    assert.ok(readFileSync(join(cwd, 'agents-2-usage.txt'), 'utf8').includes('outcome: completed'));
    for (const [number, outcome] of [[3, 'error'], [4, 'aborted']]) {
      faux.setResponses([fauxAssistantMessage('', { stopReason: outcome, errorMessage: 'synthetic failure' })]);
      await session.prompt('Exercise a terminal outcome.');
      await session.waitForIdle();
      assert.ok(readFileSync(join(cwd, `agents-${number}-usage.txt`), 'utf8').includes(`outcome: ${outcome}`));
      assert.ok(readFileSync(join(cwd, `agents-${number}-time.txt`), 'utf8').includes(`outcome: ${outcome}`));
    }
  } finally {
    session?.dispose();
    rmSync(cwd, { recursive: true, force: true });
  }
});
