# [ArkType][arktype:docs]

## [constrained objects][arktype:objects]

```ts
import { type, scope } from "arktype"

Record = type({
    "+": "reject",
    id: "string.uuid",
    label: "string > 0",
    "note?": "string",
    enabled: "boolean = true",
})
type RecordInput = typeof Record.inferIn
type RecordOutput = typeof Record.infer
```

## [validation results][arktype:traversal]

```ts
readRecord(input: unknown)
    result = Record(input)
    if result instanceof type.errors
        → { ok: false, summary: result.summary, problems: result.flatProblemsByPath }
    → { ok: true, value: result }

assertRecord = Record.assert // validated output or TraversalError
isRecordInput = Record.allows // input type guard; no defaults or morphs applied
```

## [validated morph pipelines][arktype:morphs]

```ts
ParsedRecord = type("string")
    .pipe.try((text): unknown => JSON.parse(text))
    .to({
        label: "string.trim |> string > 0",
        count: "string.numeric.parse |> number.integer >= 0",
    })

type ParsedInput = typeof ParsedRecord.inferIn // string
type ParsedOutput = typeof ParsedRecord.infer // { label: string; count: number }
value = ParsedRecord.assert('{"label":" sample ","count":"3"}')
```

## [cross-field predicates][arktype:expressions]

```ts
Interval = type({ start: "number", end: "number" })
    .narrow((value, ctx) =>
        value.start <= value.end ||
        ctx.reject({ expected: "at least start", path: ["end"] })
    )
```

## [object composition][arktype:objects]

```ts
Summary = Record.pick("id", "label")
Versioned = Summary.merge({ version: "number.integer >= 1" })
Patch = Versioned.omit("id", "version").partial()
Label = Versioned.get("label")
Keys = Versioned.keyof()
```

## [discriminated unions][arktype:expressions]

```ts
Outcome = type({
    status: "'success'",
    value: "string.numeric.parse",
}).or({
    status: "'failure'",
    message: "string > 0",
})
type Outcome = typeof Outcome.infer

describeOutcome(value: Outcome)
    switch value.status
        case "success" → value.value.toFixed(2)
        case "failure" → value.message
```

## [recursive scopes][arktype:scopes]

```ts
graph = scope({
    Node: { id: "string", edges: "Edge[]" },
    Edge: { target: "Node", weight: "number >= 0" },
}).export()

type Node = typeof graph.Node.infer
node = graph.Node.assert(input)
```

## [constrained generics][arktype:generics]

```ts
boundedList = type("<items extends unknown[]>", "0 < items <= 100")
EmailBatch = boundedList("string.email[]")
type EmailBatch = typeof EmailBatch.infer
batch = EmailBatch.assert(input)
```

## [validated functions][arktype:functions]

```ts
join = type.fn("string", "...", "string[]", ":", "string")(
    (separator, ...parts) => parts.join(separator)
)

joined = join(", ", "one", "two")
parameters = join.params
returns = join.returns
```

## [input and output json schemas][arktype:json-schema]

```ts
Length = type("string")
    .pipe(text => text.length)
    .to("number.integer >= 0")

inputSchema = Length.in.toJsonSchema()
outputSchema = Length.out.toJsonSchema()
draft07 = Length.out.toJsonSchema({ target: "draft-07" })
```

## refs

[arktype:docs]: https://arktype.io/docs/intro/setup

[arktype:objects]: https://arktype.io/docs/objects
    Optional properties cannot be present with the value undefined

[arktype:traversal]: https://arktype.io/docs/traversal-api
    data satisfies the type's constraints without applying morphs or transformations

[arktype:morphs]: https://arktype.io/docs/intro/morphs-and-more
    if one of your morphs or narrows throws, you intend to crash

[arktype:expressions]: https://arktype.io/docs/expressions

[arktype:scopes]: https://arktype.io/docs/scopes

[arktype:generics]: https://arktype.io/docs/generics

[arktype:functions]: https://arktype.io/docs/blog/2.2

[arktype:json-schema]: https://arktype.io/docs/configuration#tojsonschema

[arktype:release]: https://github.com/arktypeio/arktype/releases/tag/arktype@2.2.3
