# [clerk][@clerk/clerk-js:docs]

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

## refs

[@clerk/clerk-js:docs]: https://clerk.com/docs/js-frontend/getting-started/quickstart
