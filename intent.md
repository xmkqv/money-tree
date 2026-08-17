# intent

## outcome

- the bot trades live through Alpaca and stays inside its declared risk limits
- the dashboard shows the live state to authenticated Railway OAuth users only
- no other outcome justifies code, documentation, or configuration

## method

Two passes over the whole repository. Each pass has two phases.

1. drop: score every spec row, document, name, comment, and code block; remove what is
   redundant, useless, or wrong; a stub may replace logic the outcome does not need yet
2. distill: research the installed package APIs; reimplement, condense, move, or
   consolidate modules while the outcome holds

## control

- the orchestrator writes directive files and passes them to agents in place of conversation
- research agents run on Sonnet; implementation agents run on Opus
- a background checkpoint agent commits changes periodically
- the orchestrator answers for the final code quality
