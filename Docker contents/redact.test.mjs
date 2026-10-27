import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createJiti } from 'jiti';

// Image run: start the container with fake keys so they are in /proc/*/environ, as in real runs.
const image = process.env.PI_NETWORK_IMAGE_TEST;
const jiti = createJiti(import.meta.url);
const { default: redaction, redact, redactingOperations } = await jiti.import(image ? '/opt/pi/extensions/redact.ts' : './redact.ts');
const canaries = image ? ['DEEPSEEK_API_KEY', 'BRAVE_SEARCH_API_KEY', 'NASA_API_KEY'].map(name => process.env[name]) : [];

test('redacts secret values in text, split shell output, tool results and messages', async () => {
  const old = process.env.NASA_API_TOKEN;
  try {
    process.env.NASA_API_TOKEN = 'canary-unit-0123456789';
    process.env.SHORT_KEY = 'abc';
    assert.equal(redact('a canary-unit-0123456789 b abc'), 'a [REDACTED] b abc');
    const chunks = [];
    const operations = redactingOperations({ async exec(_command, _cwd, { onData }) {
      for (const part of ['x=canary-un', 'it-0123456789\ny=canary-', 'unit-0123456789']) onData(Buffer.from(part));
      return { exitCode: 0 };
    } });
    assert.deepEqual(await operations.exec('env', '/', { onData: data => chunks.push(data) }), { exitCode: 0 });
    assert.equal(Buffer.concat(chunks).toString(), 'x=[REDACTED]\ny=[REDACTED]');
    const handlers = new Map();
    redaction({ on: (name, handler) => handlers.set(name, handler) });
    const leaked = { content: [{ type: 'text', text: 'canary-unit-0123456789' }] };
    assert.deepEqual(handlers.get('tool_result')(leaked).content, [{ type: 'text', text: '[REDACTED]' }]);
    assert.equal(handlers.get('tool_result')({ content: [{ type: 'text', text: 'clean' }] }), undefined);
    const message = { role: 'assistant', content: [{ type: 'text', text: 'key canary-unit-0123456789' }], errorMessage: 'bad canary-unit-0123456789' };
    assert.deepEqual(handlers.get('message_end')({ message }).message, { ...message, content: [{ type: 'text', text: 'key [REDACTED]' }], errorMessage: 'bad [REDACTED]' });
  } finally {
    delete process.env.SHORT_KEY;
    if (old === undefined) delete process.env.NASA_API_TOKEN;
    else process.env.NASA_API_TOKEN = old;
  }
});

test('image keeps fake keys out of both shells and the saved session file', { skip: !image }, async () => {
  assert.ok(canaries.every(value => value?.startsWith('canary-')), 'start the container with canary-* keys');
  const { mkdtempSync, readdirSync, readFileSync, rmSync } = await import('node:fs');
  const { tmpdir } = await import('node:os');
  const { join } = await import('node:path');
  const { createAgentSession, DefaultResourceLoader, SessionManager, SettingsManager } = await import('@earendil-works/pi-coding-agent');
  const { fauxProvider, fauxAssistantMessage, fauxToolCall } = await import('@earendil-works/pi-ai');
  const { default: webSearch } = await jiti.import('/opt/pi/extensions/web-search.ts');
  const tools = new Map(), handlers = new Map();
  webSearch({ registerTool: tool => tools.set(tool.name, tool), on: (name, handler) => handlers.set(name, handler) });
  const userOperations = handlers.get('user_bash')().operations;

  // The shell gets no credentials, but CAD/FEA settings survive.
  const check = 'env; python -c "import gmsh; print(\'gmsh-ok\')"';
  let userOutput = '';
  await userOperations.exec(check, '/workspace', { onData: data => { userOutput += data; } });
  const agentOutput = (await tools.get('bash').execute('env', { command: check })).content[0].text;
  for (const output of [userOutput, agentOutput]) {
    assert.doesNotMatch(output, /^[A-Z_]*(KEY|TOKEN|SECRET)[A-Z_]*=/m);
    assert.match(output, /^PYTHONPATH=\/opt\/gmsh\/lib$/m);
    assert.match(output, /gmsh-ok/);
  }

  const cwd = mkdtempSync(join(tmpdir(), 'pi-redact-'));
  let session;
  try {
    const faux = fauxProvider({ tokensPerSecond: 100000 });
    faux.setResponses([
      fauxAssistantMessage(fauxToolCall('bash', { command: 'tr "\\0" "\\n" < /proc/$PPID/environ; tr "\\0" "\\n" < /proc/1/environ' }), { stopReason: 'toolUse' }),
      fauxAssistantMessage(fauxToolCall('read', { path: '/proc/self/environ' }), { stopReason: 'toolUse' }),
      fauxAssistantMessage(`The keys are ${canaries.join(' ')}`),
    ]);
    const agentDir = join(cwd, 'agent'), sessionDir = join(cwd, 'sessions');
    const loader = new DefaultResourceLoader({ cwd, agentDir, noExtensions: true,
      additionalExtensionPaths: ['/opt/pi/extensions/metering.ts', '/opt/pi/extensions/web-search.ts', '/opt/pi/extensions/redact.ts'],
      extensionFactories: [pi => pi.registerProvider(faux.provider)] });
    await loader.reload();
    assert.deepEqual(loader.getExtensions().errors, []);
    ({ session } = await createAgentSession({ cwd, agentDir, resourceLoader: loader, model: faux.getModel(),
      sessionManager: SessionManager.create(cwd, sessionDir), settingsManager: SettingsManager.inMemory({ retry: { enabled: false }, compaction: { enabled: false } }) }));
    await session.prompt(`My key is ${canaries[0]}. Dump the environment.`);
    await session.waitForIdle();
    await session.executeBash('tr "\\0" "\\n" < /proc/$PPID/environ', undefined, { operations: userOperations });

    const saved = readdirSync(sessionDir, { recursive: true }).filter(name => name.endsWith('.jsonl'))
      .map(name => readFileSync(join(sessionDir, name), 'utf8')).join('\n');
    // The /proc dumps did run and reach the log, just without the values.
    assert.match(saved, /DEEPSEEK_API_KEY=\[REDACTED\]/);
    assert.match(saved, /bashExecution/);
    for (const canary of canaries) assert.ok(!saved.includes(canary), `session file leaked ${canary.slice(0, 14)}`);
  } finally {
    session?.dispose();
    rmSync(cwd, { recursive: true, force: true });
  }
});
