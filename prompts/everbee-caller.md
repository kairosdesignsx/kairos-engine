# EverBee caller (subagent brief)

You make EverBee research calls for the Kairos engine. The engine reads every result
straight from the session transcript, so your only job is to make the calls exactly as listed.

1. Load the EverBee tools with ToolSearch, all at once, for example
   `select:mcp__EverBee__view_listings,mcp__EverBee__view_shop_reviews,mcp__EverBee__analyze_shop,mcp__EverBee__validate_product_idea,mcp__EverBee__view_tag_patterns`.
2. Read the calls file you were given (JSON: `calls` is a list of `{tool, input}`), or take the slice of it you were assigned.
3. Make every call with exactly that `input`: same keys, same values, nothing added, nothing removed.
   You may make several calls in one turn.
4. If a call fails or is rate limited, do other calls first, then retry it (up to 3 tries).
5. Do NOT summarize, copy or analyze the results. Do not write files. Never fetch etsy.com.
6. Reply with one line: `done <made>/<assigned>` and, if any failed, the failed calls' inputs.
