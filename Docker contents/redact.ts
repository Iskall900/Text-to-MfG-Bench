import type { BashOperations, ExtensionAPI } from '@earendil-works/pi-coding-agent';

// Same name rule as offline-shell.c. Values under 8 characters are not credentials and would over-redact.
function secrets() {
  const values = Object.entries(process.env)
    .filter(([name, value]) => /KEY|TOKEN|SECRET/i.test(name) && value && value.length >= 8)
    .map(([, value]) => value as string);
  // The JSON-escaped form matters when redacting serialized messages.
  return [...new Set(values.flatMap(value => [value, JSON.stringify(value).slice(1, -1)]))];
}

// ponytail: literal match only; an encoded or split-up key gets through, and stopping that needs separate users.
export function redact(text: string) {
  for (const secret of secrets()) text = text.split(secret).join('[REDACTED]');
  return text;
}

function redactJson<T>(value: T): T {
  const json = JSON.stringify(value), clean = redact(json);
  return clean === json ? value : JSON.parse(clean);
}

// Redacts streamed shell output one line at a time, so a key can't be split across two chunks.
export function redactingOperations(operations: BashOperations): BashOperations {
  return {
    async exec(command, cwd, options) {
      let pending = Buffer.alloc(0);
      const emit = (data: Buffer) => { if (data.length) options.onData(Buffer.from(redact(data.toString('latin1')), 'latin1')); };
      const onData = (data: Buffer) => {
        pending = Buffer.concat([pending, data]);
        const end = Math.max(pending.lastIndexOf(10), pending.lastIndexOf(13)) + 1;
        if (end) { emit(pending.subarray(0, end)); pending = pending.subarray(end); }
      };
      try { return await operations.exec(command, cwd, { ...options, onData }); }
      finally { emit(pending); }
    },
  };
}

export default function redaction(pi: ExtensionAPI) {
  // Covers every tool, including read on /proc/self/environ, which runs inside Pi rather than the shell.
  pi.on('tool_result', event => {
    const clean = redactJson({ content: event.content, structuredContent: event.structuredContent });
    return clean.content === event.content ? undefined : clean;
  });
  // Covers user prompts and model replies, for example a provider error that repeats a key.
  pi.on('message_end', event => {
    const message = redactJson(event.message);
    return message === event.message ? undefined : { message };
  });
}
