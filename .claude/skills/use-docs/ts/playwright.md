# [playwright][@playwright/test:docs]

## config

```ts
import { defineConfig } from "@playwright/test"

export default defineConfig({
    testDir: "tests",
    fullyParallel: true,
    workers: process.env.CI ? 1 : undefined,   // default is 50% of logical cores
    retries: process.env.CI ? 2 : 0,
    use: { baseURL: "http://localhost:3000", trace: "on-first-retry" },
    webServer: {
        command: "npm run start",
        url: "http://localhost:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
    },
})
```

## fixture

```ts
import { test as base } from "@playwright/test"

export const test = base.extend<{ world: World }>({
    world: async ({ page }, use) => {
        const world = await World.open(page)
        await use(world)
        await world.close()
    },
})
```

## refs

[@playwright/test:docs]: https://playwright.dev/docs/intro

[@playwright/test:configuration]: https://playwright.dev/docs/test-configuration

[@playwright/test:test-config]: https://playwright.dev/docs/api/class-testconfig

[@playwright/test:ci]: https://playwright.dev/docs/ci

[@playwright/test:web-server]: https://playwright.dev/docs/test-webserver
