"""Harvest MCP tool results straight from Claude session transcripts.

Every tool call a session (or its subagents) makes is saved verbatim in
~/.claude/projects/<cwd-slug>/<session>.jsonl and <session>/subagents/*.jsonl.
Reading them here means EverBee data reaches the engine exactly as returned,
with no retyping by the model.
"""
import glob, json, os

ROOT = os.path.expanduser('~/.claude/projects')


def transcripts(since=None):
    files = glob.glob(f'{ROOT}/*/*.jsonl') + glob.glob(f'{ROOT}/*/*/subagents/*.jsonl')
    if since:
        files = [f for f in files if os.path.getmtime(f) >= since]
    return files


def _text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return ''.join(b.get('text', '') for b in content if isinstance(b, dict))
    return ''


def calls(prefix='mcp__EverBee__', since=None):
    """Yield (tool, input, result_text, timestamp) for every finished call whose name starts with prefix."""
    for f in transcripts(since):
        uses = {}
        for line in open(f, errors='ignore'):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            c = (d.get('message') or {}).get('content')
            if not isinstance(c, list):
                continue
            for b in c:
                if not isinstance(b, dict):
                    continue
                if b.get('type') == 'tool_use' and b.get('name', '').startswith(prefix):
                    uses[b['id']] = (b['name'], b.get('input') or {})
                elif b.get('type') == 'tool_result' and b.get('tool_use_id') in uses:
                    name, inp = uses.pop(b['tool_use_id'])
                    text = _text(b.get('content'))
                    if b.get('is_error') or not text.lstrip().startswith('{'):
                        continue  # errors and rate limits are not results
                    yield name, inp, text, d.get('timestamp')


def widget(text):
    """Parse an EverBee widget payload. Returns (state, metrics, texts)."""
    try:
        w = json.loads(text)
    except ValueError:
        return None, {}, []
    metrics, texts = {}, []

    def walk(n):
        if isinstance(n, dict):
            if n.get('type') == 'Metric':
                metrics[n.get('label')] = n.get('value')
            if n.get('type') in ('Text', 'Span') and isinstance(n.get('content'), str):
                texts.append(n['content'])
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(w.get('view'))
    return w.get('state') or {}, metrics, texts


if __name__ == '__main__':
    import collections, sys
    cnt = collections.Counter(name for name, *_ in calls())
    for k, v in cnt.most_common():
        print(f'{v:5d}  {k}')
