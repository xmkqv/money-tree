# clerk

## client with ui

```ts
import { Clerk } from "@clerk/clerk-js"
import { ui } from "@clerk/ui"
clerk = new Clerk(publishableKey)
await clerk.load({ ui })
```

## session subscription

```ts
stop = clerk.addListener(({ session }) => render(session))
onDispose(() => stop())
```

## mounted sign-in

```ts
clerk.mountSignIn(element)
onDispose(() => clerk.unmountSignIn(element))
```

## mounted pricing

```ts
clerk.mountPricingTable(element, { for: "user", newSubscriptionRedirectUrl: redirectUrl })
onDispose(() => clerk.unmountPricingTable(element))
```

## tips

- the [npm client][quickstart] loads ui separately through `@clerk/ui`.
- session state is available after `load()` resolves.
- plan and feature slugs are case-sensitive.
- secret keys belong to the backend sdk; browser clients use publishable keys.

## refs

[quickstart]: https://clerk.com/docs/js-frontend/getting-started/quickstart
