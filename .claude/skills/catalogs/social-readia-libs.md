# social-readia-libs

| link | last active | stars | developer experience | feature tags |
|---|---:|---:|---|---|
| [ark ui](https://github.com/chakra-ui/ark) | 2026-08-12 | 5,340 | adopt tags input; already installed; replace custom interest keyboard and focus code | solid, tags input, accessibility, forms |
| [openrouter sdk](https://github.com/OpenRouterTeam/typescript-sdk) | 2026-08-12 | 237 | adopt version 1.2; typed chat, embeddings, errors, and transport retries | chat, embeddings, retry, typescript |
| [ai sdk](https://github.com/vercel/ai) | 2026-08-12 | 26,141 | reject for this migration; broader than the selected provider sdk | llm, structured output, embeddings, retry |
| [openrouter ai provider](https://github.com/OpenRouterTeam/ai-sdk-provider) | 2026-07-23 | 674 | reject because the selected sdk connects to openrouter directly | openrouter, routing, output, embeddings |
| [tanstack ai](https://github.com/TanStack/ai) | 2026-08-12 | 2,983 | reject for this migration; younger alternative to the selected sdk | llm, openrouter, structured output, solid |
| [msw](https://github.com/mswjs/msw) | 2026-07-24 | 18,139 | evaluate for replacing custom fetch doubles across network tests | api mocking, node, fetch, testing |
| [ky](https://github.com/sindresorhus/ky) | 2026-07-06 | 17,020 | reject after sdk adoption; one tweet client does not justify a wrapper | fetch, json, retry, timeout |
| [ofetch](https://github.com/unjs/ofetch) | 2026-08-11 | 5,350 | reject after sdk adoption; one tweet client does not justify a wrapper | fetch, json, retry, query |
| [html to epub](https://github.com/lesjoursfr/html-to-epub) | 2026-08-03 | 68 | keep; already installed and replaces epub packaging machinery | epub, xhtml, metadata, navigation |
| [fflate](https://github.com/101arrowz/fflate) | 2026-05-16 | 2,972 | keep; already installed and provides deterministic archive finalization | zip, deterministic, compression |
| [resend](https://github.com/resend/resend-node) | 2026-08-12 | 943 | keep; already installed and removes raw email transport code | email, attachment, delivery |
| [twitterapiio](https://github.com/petrbela/twitterapiio-node) | 2026-05-24 | 0 | watch; matches the provider but remains too immature to replace fetch | x search, provider sdk, typescript |
| [atproto](https://github.com/bluesky-social/atproto) | 2026-08-12 | 9,583 | future source adapter; generated types can replace search and mapping code | bluesky, search, feeds, federation |
| [feedsmith](https://github.com/macieklamberski/feedsmith) | 2026-08-10 | 615 | future feed adapter; replaces format detection, parsing, and normalization | rss, atom, json feed, opml |
| [defuddle](https://github.com/kepano/defuddle) | 2026-08-03 | 8,937 | future article adapter; replaces extraction, metadata, and markdown conversion | readability, markdown, metadata, articles |
| [fedify](https://github.com/fedify-dev/fedify) | 2026-08-05 | 1,019 | future publishing adapter; useful only if editions become federated posts | activitypub, discovery, signatures, queues |
| [xdk](https://github.com/xdevplatform/xdk-typescript) | 2026-07-25 | 65 | reject without a move to the official x api | x api, typed search, sdk |
| [twitter api v2](https://github.com/PLhery/node-twitter-api-v2) | 2026-08-04 | 1,562 | reject without a provider move; otherwise replaces raw search and paging | x api, search, paging, typescript |
| [better auth](https://github.com/better-auth/better-auth) | 2026-08-11 | 29,518 | reject until durable storage exists; sessions would increase current code | auth, magic link, sessions, rate limit |
| [tanstack form](https://github.com/TanStack/form) | 2026-08-12 | 6,651 | reject; native posts and server actions are smaller for current forms | forms, validation, solid, typescript |
| [modular forms](https://github.com/fabian-hiller/modular-forms) | 2026-06-06 | 1,212 | reject; adapters would outweigh the current native form state | forms, validation, solid, typescript |
| [tanstack query](https://github.com/TanStack/query) | 2026-08-12 | 50,113 | reject; duplicates solidstart route loading for three small route reads | server state, cache, async, solid |
| [p retry](https://github.com/sindresorhus/p-retry) | 2026-03-26 | 1,025 | reject; two small retry loops do not justify another dependency | retry, backoff, abort, async |
| [envalid](https://github.com/af/envalid) | 2026-06-10 | 1,580 | reject; duplicates installed environment validation | environment, validation, bun, typescript |
| [hdbscan ts](https://github.com/GeLi2001/hdbscan-ts) | 2026-02-14 | 12 | reject; cosine behavior regresses the current clustering path | cluster, outliers, distance |
| [mdast parser](https://github.com/syntax-tree/mdast-util-from-markdown) | 2026-06-03 | 287 | reject; a full markdown ast is too broad for citation links | markdown, ast, parser |
| [markdown it](https://github.com/markdown-it/markdown-it) | 2026-08-12 | 21,802 | reject; a full markdown renderer is too broad for citation links | markdown, tokens, renderer |
| [date fns tz](https://github.com/date-fns/tz) | 2026-05-21 | 267 | reject; native intl is smaller for one london date rule | dates, iana zones, formatting |
| [luxon](https://github.com/moment/luxon) | 2026-08-09 | 16,436 | reject; native intl is smaller for one london date rule | dates, iana zones, formatting |
| [remeda](https://github.com/remeda/remeda) | 2026-08-12 | 5,412 | reject; current collection policy code is smaller | collections, sort, sum, take |
| [es toolkit](https://github.com/toss/es-toolkit) | 2026-08-10 | 11,286 | reject; current collection policy code is smaller | utilities, sort, sum, take |
