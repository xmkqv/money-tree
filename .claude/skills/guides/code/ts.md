# ts

## form

- ts:form:code`*`
- tsx:form:code`*`

## exports

- a module has one primary export

### fns module

- a `fns` module holds one operation as its default export
- a fns module must be named clearly
- a fns module name must be immediately understandable in isolation
- a fns module does not have side-effects on program state (though it may, for example, generate decoupled files)
- a fns module may import libs

Example: `getEnvKey.ts`

```ts
export default (key: string) => typia.assert<string>(process.env[key]);
```

Example: `normalizeText.ts`

```ts
export default (params?: ...) => {
  ...
  return ...
};
```

Example: `panicIf.ts` (may be useful to declare as a function, e.g. for return casting)

```ts
function panicIf(condition: boolean, msg: string) {
  if (condition) throw new Error(`**panic**\n${msg}`);
}

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

- an import that leaves the module's subtree uses the package subpath alias
- an import of a co-module or a module below it is relative
- relative paths point down; `../` does not occur

```ts
import shelf from "./shelf";

type ShelfApi = typeof shelf;
```

```ts
import getThing from "~/fns/getThing";
```
