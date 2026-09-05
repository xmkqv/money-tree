# ts storybook

[ts](../code/ts.md)
[catalog](../../catalogs/vite-solidjs.md)
[Storybook documentation](https://storybook.js.org/docs)

- use `storybook@^10.5`
- use Node 20.19 or 22.12 or later
- keep `.storybook/main.ts` and every preset valid ESM
- run the official automigration before manual migration work and review every remaining change
- use CSF 3 as the stable story format; do not adopt CSF Next without an explicit preview migration
- keep framework packages and community adapters on compatible Storybook 10 releases
- for Solid, use the community `storybook-solidjs-vite` adapter and a Vite 5 through 8 project

## stories

- make each story demonstrate one concept or use case
- explain when and why the story matters in its description
- document component props so generated manifests remain useful
- use story-level globals for fixed themes, locales, and viewports
- use preview decorators for shared providers, global CSS, portals, and stable mocks
- exclude irrelevant or deprecated stories from manifests
- keep manifest context small enough for an agent to select relevant stories

```ts
import type { Meta, StoryObj } from "storybook-solidjs-vite";

import Button from "./Button";

const meta = {
  component: Button,
  tags: ["autodocs", "stable"],
} satisfies Meta<typeof Button>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: { label: "Borrow" },
};
```

## tags

- use `dev`, `manifest`, and `test` as the inherited built-in tags
- remove an inherited tag with its `!` prefix
- use custom tags for status, ownership, or a stable product dimension
- do not use tags as a substitute for clear story names
