# [typia][typia:docs]

## reusable validators

```ts
import typia from "typia"
isValue = typia.createIs<Value>()
assertValue = typia.createAssert<Value>()
validateValue = typia.createValidate<Value>()
values.map(value => assertValue(value))
```

## exact shape

```ts
assertExact = typia.createAssertEquals<Value>()
value = assertExact(input)
```

## tagged constraints

```ts
import type { tags } from "typia"
type Value = {
    id: string & tags.Format<"uuid">
    count: number & tags.Type<"uint32"> & tags.Minimum<1>
    label: string & tags.MinLength<1>
}
```

## assertion guard

```ts
import type { AssertionGuard } from "typia"
const guard: AssertionGuard<Value> = typia.createAssertGuard<Value>()
guard(input)
```

## structured validation

```ts
result = validateValue(input)
if result.success
    consume(result.data)
else
    result.errors.forEach(error => report(error.path, error.expected, error.value))
```

## validated json

```ts
value = typia.json.assertParse<Value>(text)
text = typia.json.assertStringify<Value>(value)
schema = typia.json.schemas<[Value]>()
```

## refs

[typia:docs]: https://typia.io/docs/

[typia:setup]: https://typia.io/docs/setup/
    your build has to run through the TypeScript 7 transformer path
    The stock `tsc`, `ts-node`, and `tsx` commands do not load typia's transform.

[typia:json]: https://typia.io/docs/json/parse/
    JSON can't represent everything TypeScript can
