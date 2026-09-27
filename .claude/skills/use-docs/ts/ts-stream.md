# [ts-stream][ts-stream:docs]

## registered emitter

```ts
import stream, { segment } from "ts-stream"

const CLOSE = "^panel/close$"
const PAN = "^space/(?<id>[^/]+)/pan/(?<x>-?\\d+)/(?<y>-?\\d+)$"
spaces = stream.register(CLOSE, PAN)
```

## pattern listener

```ts
stop = spaces.on(PAN, ({ id, x, y }) => pan(segment.decode(id), Number(x), Number(y)))
stop()
```

## typed action

```ts
spaces.emit(`space/${segment.encode(id)}/pan/1/2`)
type Pan = Action<typeof PAN>
type PanPayload = Payload<typeof PAN>
```

## literal segment

```ts
const MODE = "read|edit"
const SET_MODE = `^doc/(?<id>[^/]+)/mode/(?<mode>${MODE})$` as const
docs = stream.register(SET_MODE)
docs.on(SET_MODE, ({ mode }) => setMode(mode))
```

## text listener

```ts
stop = stream.on(action => log(action))
```

## refs

[ts-stream:docs]: https://github.com/xmkqv/ts-stream
    a pattern is anchored `^…$`; a top-level `|` throws, wrap it `(?:a|b)`
    a segment reaches its listener as text and is never coerced
    encode a value with segment.encode so it occupies one segment
    the registry is global; dispose listeners with the owner
    an action that matches no declared pattern throws at the sender

[ts-stream:arkregex]: https://arktype.io/docs/blog/arkregex
    a literal alternation narrows a segment; a character class widens it to string
    a template literal pattern needs `as const` to keep its literal type
