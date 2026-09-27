# [storybook for solid][storybook-solidjs-vite:docs]

## config

```ts
// .storybook/main.ts
import { defineMain } from "storybook-solidjs-vite"
export default defineMain({ framework: "storybook-solidjs-vite", stories: ["../src/**/*.stories.tsx"] })
```

## jsx decorator (mounts once, context is reactive)

```tsx
import { createJSXDecorator } from "storybook-solidjs-vite"
const withProvider = (value: Service) =>
    createJSXDecorator((Story) => <Ctx.Provider value={value}><Story /></Ctx.Provider>)
```

## side-effect decorator (re-runs per update)

```ts
import { createDecorator } from "storybook-solidjs-vite"
const applyScheme = createDecorator((Story, context) => {
    document.documentElement.style.colorScheme = String(context.globals.scheme)
    return Story()
})
```

## package-owned fake behind the provider

```ts
// pkg/src/fake.ts, exported as "pkg/fake"
export default function fakeService(overrides: Partial<Service> = {}): Service {
    return { ...defaults, ...overrides } satisfies Service
}
```

## recorded callbacks

```ts
import { fn } from "storybook/test"
const onSubmit = fn()
export const Primary: Story = { args: { onSubmit } }
```

## reactive render

```tsx
export const Live: Story = { render: (args) => <Component label={args.label} /> }  // args is a store
```

## refs

[storybook-solidjs-vite:docs]: https://github.com/solidjs-community/storybook
    JSX decorators re-run can leave duplicate DOM nodes

[storybook:decorators]: https://storybook.js.org/docs/writing-stories/decorators

[storybook:mocking-providers]: https://storybook.js.org/docs/writing-stories/mocking-data-and-modules/mocking-providers

[storybook:mocking-modules]: https://storybook.js.org/docs/writing-stories/mocking-data-and-modules/mocking-modules

[storybook:portable-stories]: https://storybook.js.org/docs/api/portable-stories/portable-stories-vitest
    This API should be called once, before the tests run, typically in a setup file.

[martinfowler:test-double]: https://martinfowler.com/bliki/TestDouble.html
