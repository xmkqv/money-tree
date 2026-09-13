# storybook

## typed csf story

```ts
import type { Meta, StoryObj } from "storybook-solidjs-vite"
meta = { component: Component, tags: ["autodocs"] } satisfies Meta<typeof Component>
export default meta
type Story = StoryObj<typeof meta>
export const Primary: Story = { args: { label: "Example" } }
```

## shared provider

```tsx
meta = {
    component: Component,
    decorators: [Story => <Provider><Story /></Provider>],
} satisfies Meta<typeof Component>
```

## story documentation

```ts
export const Disabled: Story = {
    args: { disabled: true },
    parameters: { docs: { description: { story: "Disabled interaction state." } } },
}
```

## tag selection

```ts
export const Internal: Story = {
    tags: ["!autodocs"],
    args: { label: "Example" },
}
```

## tips

- the [csf form][csf] binds story args to the component's inferred props.
- the example uses the solidjs-vite adapter; type imports follow the selected framework.
- decorators supply shared providers around stories.
- `!tag` removes an inherited tag.
- story parameters hold documentation and addon configuration.

## refs

[csf]: https://storybook.js.org/docs/api/csf
