# ts typia

[ts](../code/ts.md)
[typia documentation](https://typia.io/docs/)

- use `typia@^14`, `ttsc@^0.28`, and `@ttsc/unplugin@^0.28` with typescript 7
- use `typia@^12` with `typescript@6` and `ts-patch` only when typescript 7 is out of reach

## setup

typia is a compile-time transformer. The TypeScript type is the source. The compiler
writes the validator. Keep `strict` on. Do not add `compilerOptions.plugins`; `ttsc`
finds the transform in `typia/package.json`.

Example: `package.json`

```jsonc
{
  "scripts": { "lint": "biome check --write . && ttsc" },
  "dependencies": { "typia": "14" },
  "devDependencies": { "@ttsc/unplugin": "0.28", "ttsc": "0.28", "typescript": "7" }
}
```

Example: `vite.config.ts`

```ts
import ttsc from "@ttsc/unplugin/vite";

export default defineConfig({
  plugins: [ttsc(), solidPlugin()],
});
```

- `@ttsc/unplugin` and `ttsc` both declare `enforce: "pre"`. Array order decides.
  Put `ttsc()` before each plugin that reads the transformed source.
- `@ttsc/unplugin` peer-pins `ttsc` to its own minor. Move both versions together.
- entrypoints are `@ttsc/unplugin/{vite,rollup,rolldown,esbuild,webpack,rspack,next,turbopack,farm,bun}`
- the bun runtime adds `preload = ["@ttsc/unplugin/bun-register"]` to `bunfig.toml`
- `ttsx` overrides `noEmit`. A project with `allowImportingTsExtensions` and
  `noEmit` fails with TS5096 under `ttsx`. Use `ttsc --noEmit` to check such a project.

Stock `tsc` type-checks each typia call and reports no error. Stock `tsc` does not
transform. A green `tsc --noEmit` can hide code that fails at runtime with
`Error on typia.assert(): no transform has been configured.` Move every check
entrypoint to `ttsc`.

```bash
ttsc
ttsc --noEmit
ttsx src/x.ts
```

`ttsc` builds, `ttsc --noEmit` checks only, and `ttsx` executes a file.

## validators

```ts
import typia from "typia";

typia.is<T>(input);
typia.assert<T>(input);
typia.assertGuard<T>(input);
typia.validate<T>(input);
```

`is` returns a boolean and narrows through `input is T`. `assert` returns the input
or throws `TypeGuardError`. `assertGuard` returns void and narrows in place.
`validate` returns `IValidation<T>` with every error path.

Each one has an `Equals` variant: `equals`, `assertEquals`, `assertGuardEquals`,
`validateEquals`. The plain form ignores an unknown key. The `Equals` form reports
it from the root down, so one call covers a nested structure.

```ts
typia.is<Point>({ x: 1, y: 2, z: 3 });
typia.equals<Point>({ x: 1, y: 2, z: 3 });
```

Pick `assert` when invalid input is exceptional. Pick `validate` when the caller
must show each field error. Pick `is` for a yes-or-no answer.

## factories

`create*` emits the generated code once at module scope. A bare
`typia.assert<T>(x)` emits a full copy at each call site. Hoist each validator
that runs more than once.

```ts
const assertUser = typia.createAssert<User>();
const assertUserEquals = typia.createAssertEquals<User>();
const isUser = typia.createIs<User>();
const validateUser = typia.createValidate<User>();
```

A factory result is `(input: unknown, errorFactory?: (props) => Error) => T`.
`Array.prototype.map` supplies the index as the second argument. Wrap the call.

```ts
rows.map((value) => assertUser(value));
```

`createValidate` implements Standard Schema, so it also fits a library that
accepts a Standard Schema validator.

`createAssertGuard` needs an explicit variable type. TypeScript cannot infer an
`asserts` signature.

```ts
import typia, { type AssertionGuard } from "typia";

const guardUser: AssertionGuard<User> = typia.createAssertGuard<User>();
```

## tags

A tag is an intersection. Tags compose with `&` and `|`. The compiler rejects a
tag that does not match its base type.

```ts
import type { tags } from "typia";

type Price = number & tags.Type<"double"> & tags.Minimum<0>;
type Email = string & tags.Format<"email">;
type Serial = string & tags.Pattern<"^SN-[0-9]+$">;
type Ids = Array<string & tags.Format<"uuid">> & tags.MinItems<1>;
type Either = string & (tags.Format<"ipv4"> | tags.Format<"ipv6">);
type Mixed = (number & tags.Type<"int32">) | (bigint & tags.Type<"uint64">);
type Percent = `${number & tags.Minimum<0> & tags.Maximum<100>}%`;
```

Import `tags` with `import type` under `verbatimModuleSyntax`.

Tags reach the emitted code as direct comparisons.

```ts
type Size = bigint & tags.Minimum<0n>;
type Ord = string & tags.MinLength<1>;
```

Define a tag with `TagBase` when no built-in tag states the rule. `validate`
holds an expression string or a function. `$input` is the value.

```ts
type Postfix<Value extends string> = tags.TagBase<{
  kind: "postfix";
  target: "string";
  value: Value;
  validate: `$input.endsWith("${Value}")`;
}>;

type IsEven = tags.TagBase<{
  kind: "isEven";
  target: "number";
  value: undefined;
  validate: (value: number) => value % 2 === 0;
}>;
```

## brands

typia accepts a phantom marker on a real base. It drops the marker and validates
the base. Use a `unique symbol` key. Accumulate the names in a record so a
narrow brand stays assignable to a wide one.

```ts
declare const brand: unique symbol;
type Brand<Name extends string> = {
  readonly [brand]: { [Key in Name]: true };
};

export type Uuid = string & tags.Format<"uuid"> & Brand<"Uuid">;
export type SpaceId = Uuid & Brand<"SpaceId">;
export type NodeId = Uuid & Brand<"NodeId">;
```

`SpaceId` is assignable to `Uuid`. `Uuid` is not assignable to `SpaceId`, and
`SpaceId` is not assignable to `NodeId`.

A required string key is real data, not a marker. typia rejects it with
`nonsensible intersection`.

```ts
type Bad = string & { __brand: "SpaceId" };
type Weak = string & { brand?: "SpaceId" };
```

`Bad` is rejected. `Weak` is accepted, but a plain string fits it.

typia mints no brand at runtime. Cast a value the code just built. Validate a
value that crosses a boundary.

```ts
const fresh = crypto.randomUUID() as SpaceId;
const fromDom = typia.assert<SpaceId>(element.dataset.tileId);
```

## no transform stage

typia validates. typia does not convert. Split a schema that changed the value
into a wire type, a validator, and a mapper.

```ts
type CamRow = { space_id: SpaceId; x: CoordinateText; y: CoordinateText };
type Cam = { space_id: SpaceId; x: Coordinate; y: Coordinate };
type CoordinateText = string & tags.Pattern<"^-?(0|[1-9][0-9]*)$">;

const camRow = typia.createAssertEquals<CamRow>();

function assertCam(value: unknown): Cam {
  const row = camRow(value);
  return { space_id: row.space_id, x: toCoordinate(row.x), y: toCoordinate(row.y) };
}

function toCoordinate(value: CoordinateText): Coordinate {
  return BigInt(value) as Coordinate;
}
```

The pattern makes `BigInt` total. Without it a malformed column throws a raw
`SyntaxError` instead of a `TypeGuardError`.

## generic limit

typia resolves the type argument at the call site. A type parameter has no type
at that point.

```ts
function read<T>(input: unknown): T {
  return typia.assert<T>(input);
}
```

Give each concrete type its own factory, or move the call to the caller.

## errors

`assert` throws `TypeGuardError` with `method`, `path`, `expected`, and `value`.
`validate` returns every error instead.

```ts
type IValidation<T> = IValidation.ISuccess<T> | IValidation.IFailure;

namespace IValidation {
  interface ISuccess<T> { success: true; data: T }
  interface IFailure {
    success: false;
    data: unknown;
    errors: { path: string; expected: string; value: unknown }[];
  }
}
```

```ts
const result = typia.validate<User>(input);
if (result.success === false)
  for (const error of result.errors)
    report(error.path, error.expected, error.value);
```

## json

```ts
typia.json.isParse<T>(text);
typia.json.assertParse<T>(text);
typia.json.validateParse<T>(text);
typia.json.stringify<T>(value);
typia.json.assertStringify<T>(value);
typia.json.schemas<[T]>();
```

`isParse` returns `T | null`, `assertParse` returns `T` or throws `TypeGuardError`, and
`validateParse` returns `IValidation<T>`. `stringify` skips the check and is faster than
`JSON.stringify`; `assertStringify` checks first. `schemas` emits JSON Schema.

Malformed text throws `SyntaxError` before any check runs. Each parse returns
`Primitive<T>`, the projection of `T` through a JSON round trip. A `Date` becomes
`string & tags.Format<"date-time">`. A `Set`, a `Map`, or a `bigint` becomes
`never`, which is a compile error at the call site.

`json.stringify` runs no check. Use it only for a value the compiler proves.

## limits

- typia checks structure. typia runs no `instanceof` for a user-defined class.
- typia skips a function-typed property. Set the `functional` transform flag to
  check it.
- `Date`, `Uint8Array`, `Set`, and `Map` are checked, including their elements.
- a `NaN` passes a plain `number`; set the `numeric` or `finite` transform flag
  to reject it.
- a local `declare module "typia"` moves each call out of typia's declarations
  The transform then skips it.

## source state

- [typia 14.0.0](https://www.npmjs.com/package/typia) declares `ttsc >=0.19.2` as
  an optional peer. [ttsc 0.28.1](https://www.npmjs.com/package/ttsc) ships the
  `ttsc`, `ttsx`, and `ttscserver` binaries.
- [PR #1970](https://github.com/samchon/typia/pull/1970), merged 2026-06-22, added
  the symbol and optional phantom brand support in this guide. It declines a
  required string-keyed brand, a template-literal intersection, and an array or
  tuple element intersection.
- issues [#911](https://github.com/samchon/typia/issues/911) and
  [#933](https://github.com/samchon/typia/issues/933) record the earlier
  `nonsensible intersection` behaviour. Read them with PR #1970 next to them.
- official documentation reviewed on 2026-08-21 for
  [setup](https://typia.io/docs/setup/),
  [tags](https://typia.io/docs/validators/tags/),
  [validate](https://typia.io/docs/validators/validate/),
  [json parse](https://typia.io/docs/json/parse/), and
  [bundlers](https://ttsc.dev/docs/ttsc/bundler/).
