# ts clerk

[ts](../code/ts.md)
[Clerk JavaScript documentation](https://clerk.com/docs/js-frontend)

- use `@clerk/clerk-js@^6` with the Core 3 API
- import shared types from Clerk shared packages; do not add deprecated `@clerk/types`
- do not use a community Solid SDK that still depends on Core 2
- create the client with the publishable key and await `load()` before reading session state or mounting UI
- keep the secret key on the server
- design authentication and billing boundaries to report Clerk unavailability explicitly

```ts
import { Clerk } from "@clerk/clerk-js";
import { ui } from "@clerk/ui";

export default async function clerkClient(publishableKey: string) {
  const clerk = new Clerk(publishableKey);
  await clerk.load({ ui });
  return clerk;
}
```

## ui components

- the npm build is headless until `load({ ui })` receives `ui` from `@clerk/ui`
- a bare `load()` makes every mount throw "Clerk was not loaded with Ui components"
- only the CDN `clerk.browser.js` build carries components on its own
- `@clerk/ui` roughly doubles the clerk bundle; budget the chunk accordingly
- unmount a mounted Clerk component when its host node leaves the document
- treat a Vite prebundle mount failure as an upstream compatibility issue; do not hide it with retries
- a session listener maps the vendor session to your own signed-in state

```ts
clerk.addListener(({ session }) => {
  if (!session) return set("signed_out");
  set({ vendor_user_id: session.user?.id ?? panic("the vendor session has no user") });
});
```

## authorization

- keep plan and feature slugs case-sensitive
- reload the session before relying on a newly changed plan or feature check
- treat webhook event names as exact values

## billing

- configure plans in Clerk; do not expect Clerk plans to synchronize with existing Stripe products
- use a separate Stripe account for production and the sandbox gateway in development
- identify a private plan by plan ID because it is not discoverable in the public pricing table
- derive the billing period from the chosen plan; do not force a monthly period
- include seat quantity and price ID when the selected plan requires them
- confirm a new card checkout with its payment token
- confirm a saved card checkout with its payment method ID

```ts
const node = document.querySelector<HTMLDivElement>("#pricing-table");
if (!node) throw new Error("pricing table target is missing");

clerk.mountPricingTable(node, {
  for: "user",
  newSubscriptionRedirectUrl: "/account",
});
```

## testing

- `@clerk/testing` playwright helpers need `clerkSetup` once and the testing token per page
- the testing token bypasses bot detection, so challenge hosts stay out of test flows
- `clerk.signIn` needs a `window.Clerk`; hotload the CDN build when the app's bundle is unexposed
- persist a worker's session with `storageState(path, indexedDB: true)` and reuse it per context
- mint test users through the backend api with `skip_password_requirement`

```ts
import { clerk, clerkSetup } from "@clerk/testing/playwright";
import { setupClerkTestingToken } from "@clerk/testing/playwright";

await clerkSetup({ publishableKey });
await setupClerkTestingToken({ page });
await page.evaluate(/* inject https://{frontendApi}/npm/@clerk/clerk-js@6/dist/clerk.browser.js, then new Clerk(key).load() */);
await clerk.signIn({ page, emailAddress: handle });
await context.storageState({ path: `.auth/${handle}.json`, indexedDB: true });
```
