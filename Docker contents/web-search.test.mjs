import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createJiti } from 'jiti';

const { default: webSearch } = await createJiti(import.meta.url).import(process.env.PI_NETWORK_IMAGE_TEST ? '/opt/pi/extensions/web-search.ts' : './web-search.ts');
const tools = new Map(), handlers = new Map();
webSearch({ registerTool: tool => tools.set(tool.name, tool), on: (name, handler) => handlers.set(name, handler) });

test('search only calls the fixed API and returns snippets, without fetching result URLs', async () => {
  const oldFetch = globalThis.fetch, oldKey = process.env.BRAVE_SEARCH_API_KEY;
  try {
    process.env.BRAVE_SEARCH_API_KEY = 'test-key';
    const calls = [];
    globalThis.fetch = async (url, options) => {
      calls.push([url, options]);
      return Response.json({ web: { results: [{ title: 'CAD', url: 'https://example.com/file.zip', description: 'snippet', extra: 'discard' }] } });
    };
    const result = await tools.get('web_search').execute('test', { query: 'cad & fea' });
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0].origin, 'https://api.search.brave.com');
    assert.equal(calls[0][0].searchParams.get('q'), 'cad & fea');
    assert.equal(calls[0][1].redirect, 'error');
    assert.equal(calls[0][1].headers['X-Subscription-Token'], 'test-key');
    assert.deepEqual(JSON.parse(result.content[0].text), [{ title: 'CAD', url: 'https://example.com/file.zip', snippet: 'snippet' }]);
    delete process.env.BRAVE_SEARCH_API_KEY;
    await assert.rejects(tools.get('web_search').execute('test', { query: 'cad' }), /BRAVE_SEARCH_API_KEY/);
    process.env.BRAVE_SEARCH_API_KEY = 'test-key';
    globalThis.fetch = async () => new Response('secret provider error', { status: 403 });
    await assert.rejects(tools.get('web_search').execute('test', { query: 'cad' }), /HTTP 403/);
    globalThis.fetch = async () => new Response('binary data', { headers: { 'content-type': 'application/octet-stream' } });
    await assert.rejects(tools.get('web_search').execute('test', { query: 'cad' }), /unexpected content type/);
    assert.ok(handlers.get('user_bash')().operations);
    assert.match(handlers.get('before_agent_start')({ systemPrompt: 'base' }).systemPrompt, /Downloads.*disabled/);
  } finally {
    globalThis.fetch = oldFetch;
    if (oldKey === undefined) delete process.env.BRAVE_SEARCH_API_KEY;
    else process.env.BRAVE_SEARCH_API_KEY = oldKey;
  }
});

test('image shell blocks network in children while preserving local computation', { skip: !process.env.PI_NETWORK_IMAGE_TEST }, async () => {
  const shell = tools.get('bash');
  const local = await shell.execute('local', { command: 'python -c "from build123d import Box; assert abs(Box(1, 2, 3).volume - 6) < 1e-9; print(42)"' });
  assert.match(local.content[0].text, /42/);
  for (const command of [
    'python -c "import socket; socket.create_connection((\'example.com\', 443))"',
    'node -e "fetch(\'https://example.com/file.zip\').then(()=>process.exit(0)).catch(()=>process.exit(9))"',
    '/opt/pi/node_modules/.bin/pi --version && python -c "import socket; socket.socket()"',
  ]) {
    const result = await shell.execute('blocked', { command });
    assert.match(result.content[0].text, /exited with code [1-9]/i);
  }
  const direct = await handlers.get('user_bash')().operations.exec('python -c "import socket; socket.socket()"', '/workspace', { onData() {} });
  assert.notEqual(direct.exitCode, 0);
});

test('image discovers both trusted extensions and exposes search in an agent session', { skip: !process.env.PI_NETWORK_IMAGE_TEST }, async () => {
  const { mkdtempSync, rmSync } = await import('node:fs');
  const { tmpdir } = await import('node:os');
  const { join } = await import('node:path');
  const { createAgentSession, DefaultResourceLoader, SessionManager, SettingsManager } = await import('@earendil-works/pi-coding-agent');
  const { fauxProvider, fauxAssistantMessage, fauxToolCall } = await import('@earendil-works/pi-ai');
  const cwd = mkdtempSync(join(tmpdir(), 'pi-search-'));
  const oldFetch = globalThis.fetch, oldKey = process.env.BRAVE_SEARCH_API_KEY;
  let session;
  try {
    process.env.BRAVE_SEARCH_API_KEY = 'test-key';
    globalThis.fetch = async () => Response.json({ web: { results: [{ title: 'fixture', url: 'https://example.com', description: 'found' }] } });
    const faux = fauxProvider({ tokensPerSecond: 100000 });
    faux.setResponses([
      fauxAssistantMessage(fauxToolCall('web_search', { query: 'cad' }), { stopReason: 'toolUse' }),
      fauxAssistantMessage('finished'),
    ]);
    const agentDir = join(cwd, 'agent');
    const loader = new DefaultResourceLoader({ cwd, agentDir, noExtensions: true,
      additionalExtensionPaths: ['/opt/pi/extensions/metering.ts', '/opt/pi/extensions/web-search.ts'],
      extensionFactories: [pi => pi.registerProvider(faux.provider)] });
    await loader.reload();
    assert.deepEqual(loader.getExtensions().errors, []);
    ({ session } = await createAgentSession({ cwd, agentDir, resourceLoader: loader, model: faux.getModel(),
      sessionManager: SessionManager.inMemory(cwd), settingsManager: SettingsManager.inMemory({ retry: { enabled: false }, compaction: { enabled: false } }) }));
    await session.prompt('Search for cad, then finish.');
    await session.waitForIdle();
    const result = session.sessionManager.getEntries().find(entry => entry.type === 'message' && entry.message.role === 'toolResult');
    assert.equal(result.message.toolName, 'web_search');
    assert.equal(result.message.isError, false);
    assert.match(result.message.content[0].text, /fixture/);
  } finally {
    session?.dispose();
    globalThis.fetch = oldFetch;
    if (oldKey === undefined) delete process.env.BRAVE_SEARCH_API_KEY;
    else process.env.BRAVE_SEARCH_API_KEY = oldKey;
    rmSync(cwd, { recursive: true, force: true });
  }
});
