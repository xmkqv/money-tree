# ts

## exports

- count(module.primary_exports) = 1

### fns module

- a `fns` module holds one operation as its default export
- a fns module name is understandable in isolation
- fns modules have no side effects on program state; decoupled file generation is allowed

Example: `getEnvKey.ts`

```ts
export default (key: string) => typia.assert<string>(process.env[key]);
```

Example: `panicIf.ts`

```ts
function panicIf(condition: boolean, message: string) { … }

export default panicIf;
```

### fns object export

- a non-component module of related operations has a default fns object export

```ts
export default {
  getEnvKey(key: string) { … },
  normalizeText(params: …) { … },
  panicIf(condition: boolean, message: string) { … },
};
```

## imports

```ts
import shelf from "./shelf";
import getThing from "~/fns/getThing";
```
