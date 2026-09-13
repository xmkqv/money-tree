# css

- preferred suffixes: `*-{sm|md|lg}`, `*-dim`, …
- preferred duration suffixes: `*-{snap|fast|slow}`
- `size-*` implies aspect-ratio 1:1

## form

- css:form:code`*`

## support

- a baseline feature may be required without a fallback
- a limited feature is an optional enhancement behind a useful fallback
- a draft feature without interoperable support stays out of a required path
- build targets are declared once

```text:browserslistrc
baseline widely available
```

[baseline with browserslist](https://web.dev/articles/use-baseline-with-browserslist)

### fallback then enhancement

```css
.card {
  padding: var(--space-md);
  padding: if(style(--density: compact): var(--space-sm); else: var(--space-md));
}
```

[if()](https://developer.chrome.com/blog/if-article)

## cascade

- an importance override is reserved for what the cascade cannot otherwise reach

### layer order

```css
@layer reset, tokens, base, layout, components, utilities;

@import url("reset.css") layer(reset);
```

### scoped component

```css
@scope (.card) to (.card-body) {
  :scope { padding: var(--space-md); }
  h2 { text-wrap: balance; }
}
```

[@scope](https://www.smashingmagazine.com/2026/02/css-scope-alternative-naming-conventions/)

## tokens

- a component exposes only the values callers are expected to tune

### primitive scale

```css
@layer tokens {
  :root {
    --brand-h: 265;
    --brand-c: 0.22;
    --space-sm: 0.5rem;
    --space-md: 1rem;
    --space-lg: 2rem;
    --size-sm: 2rem;
    --radius-md: 0.5rem;
    --text-md: clamp(1rem, 0.9rem + 0.5vi, 1.125rem);
    --text-lg: clamp(1.5rem, 1rem + 2vi, 2.5rem);
    --duration-fast: 120ms;
    --duration-slow: 400ms;
    --ease-snap: linear(0, 1.04 60%, 1);
  }
}
```

### semantic role

```css
:root {
  color-scheme: light dark;
  --color-surface: light-dark(oklch(98% 0.01 var(--brand-h)), oklch(18% 0.02 var(--brand-h)));
  --color-text: light-dark(oklch(22% 0.03 var(--brand-h)), oklch(94% 0.01 var(--brand-h)));
  --color-text-dim: oklch(from var(--color-text) l c h / 0.64);
  --color-accent: oklch(58% var(--brand-c) var(--brand-h));
  --color-accent-dim: color-mix(in oklch, var(--color-accent) 15%, var(--color-surface));
  --color-danger: oklch(58% 0.2 30);
}
```

### registered token

```css
@property --progress {
  syntax: "<number>";
  inherits: false;
  initial-value: 0;
}
```

### component contract

```css
.button {
  --_bg: var(--button-bg, var(--color-accent));
  background: var(--_bg);
  color: contrast-color(var(--_bg));
  &:hover { --_bg: oklch(from var(--_bg) calc(l - 0.08) c h); }
}
```

[contrast-color()](https://www.smashingmagazine.com/2026/05/building-self-correcting-color-systems-contrast-color/)

## reset

### layered reset

```css
@layer reset {
  *, ::before, ::after { box-sizing: border-box; }
  * { margin: 0; }
  html { scrollbar-gutter: stable; text-size-adjust: none; -webkit-text-size-adjust: none; }
  body { min-block-size: 100svh; line-height: 1.5; }
  :where(img, picture, video, canvas, svg) { display: block; max-inline-size: 100%; }
  :where(input, button, textarea, select) { font: inherit; }
  :where(h1, h2, h3, h4, p) { overflow-wrap: break-word; }
  :where(ul, ol)[role="list"] { list-style: none; padding: 0; }
  [hidden]:not([hidden="until-found"]) { display: none !important; }
}
```

## selectors

- source order stays the reading and focus order

### relational state

```css
.field:has(:user-invalid) { border-color: var(--color-danger); }
.card:has(img) { grid-template-columns: 8rem 1fr; }
```

### focus ring

```css
:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px; }
```

### ordinal stagger

```css
@keyframes fade-in { from { opacity: 0; } }
.list > * {
  animation: fade-in var(--duration-slow) var(--ease-snap) both;
  animation-delay: calc(sibling-index() * var(--duration-fast));
}
```

[sibling-index()](https://www.smashingmagazine.com/2026/05/mathematical-layouts-sibling-index-sibling-count/)

## layout

- normal flow is preferred until a requirement needs another model

### one axis

```css
.toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-sm); }
```

### two axes

```css
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 18rem), 1fr));
  gap: var(--space-md);
}
.grid > article {
  display: grid;
  grid-row: span 3;
  grid-template-rows: subgrid;
}
```

## sizing

### intrinsic box

```css
.card { inline-size: min(100%, 60ch); min-inline-size: 0; }
.page { min-block-size: 100svh; }
.thumb { inline-size: 100%; aspect-ratio: 16 / 9; object-fit: cover; }
.size-sm { inline-size: var(--size-sm); aspect-ratio: 1; }
```

### growing field

```css
textarea {
  field-sizing: content;
  min-block-size: 3rlh;
  max-inline-size: 50ch;
}
```

## responsive

- fluid sizing is tried before a breakpoint

### container size

```css
.card-list { container: cards / inline-size; }
@container cards (inline-size > 40rem) {
  .card { grid-template-columns: 1fr 2fr; }
}
```

### container style

```css
.card[data-variant="danger"] { --variant: danger; }
@container style(--variant: danger) {
  .card-title { color: var(--color-danger); }
}
```

[style queries](https://modern-css.com/container-style-queries/)

## type

### wrap and flow

```css
:where(h1, h2, h3) { text-wrap: balance; }
:where(p, li) { text-wrap: pretty; max-inline-size: 65ch; }
.prose > * + * { margin-block-start: 1lh; }
```

## color

- color is never the only signal

### contrast preference

```css
@media (prefers-contrast: more) {
  :root { --color-text-dim: var(--color-text); }
}
@media (forced-colors: active) {
  .button { border: 1px solid ButtonText; }
}
```

## native

- semantic markup is preferred before a custom control

### invokers

```html
<button commandfor="menu" command="toggle-popover">Menu</button>
<menu id="menu" popover>…</menu>
<button commandfor="settings" command="show-modal">Settings</button>
<dialog id="settings" closedby="any">…</dialog>
```

[invoker commands](https://modern-css.com/modal-controls-without-onclick-handlers/)

### dialog

```css
dialog {
  inline-size: min(100% - var(--space-lg), 40rem);
  border: 0;
  border-radius: var(--radius-md);
  &::backdrop { background: oklch(10% 0.02 var(--brand-h) / 0.5); }
}
```

### anchored popover

```css
[commandfor="menu"] { anchor-name: --menu; }
[popover] {
  margin: 0;
  position-anchor: --menu;
  position-area: block-end span-inline-end;
  position-try-fallbacks: flip-block, flip-inline;
}
```

[anchor positioning](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/position-try-fallbacks)

### disclosure

```css
details::details-content {
  opacity: 0;
  transition: opacity var(--duration-fast), content-visibility var(--duration-fast) allow-discrete;
}
details[open]::details-content { opacity: 1; }
```

## motion

- reduced motion removes non-essential movement without hiding state

### entry and exit

```css
[popover] {
  opacity: 0;
  translate: 0 var(--space-sm);
  transition:
    opacity var(--duration-fast),
    translate var(--duration-fast) var(--ease-snap),
    display var(--duration-fast) allow-discrete,
    overlay var(--duration-fast) allow-discrete;
  &:popover-open {
    opacity: 1;
    translate: 0;
    @starting-style { opacity: 0; translate: 0 var(--space-sm); }
  }
}
```

### motion opt-in

```css
@media (prefers-reduced-motion: no-preference) and (hover: hover) {
  .card { transition: translate var(--duration-fast) var(--ease-snap); }
  .card:hover { translate: 0 -2px; }
}
```

### view transition

```css
@view-transition { navigation: auto; }
.card {
  view-transition-name: match-element;
  view-transition-class: card;
}
::view-transition-group(.card) { animation-duration: var(--duration-slow); }
```

[match-element](https://www.bram.us/2026/06/19/view-transition-name-attr-or-match-element/)

### scroll driven

```css
.reveal {
  animation: fade-in linear both;
  animation-timeline: view();
  animation-range: entry 0% cover 30%;
}
```

[scroll-driven animations](https://webkit.org/blog/17101/a-guide-to-scroll-driven-animations-with-just-css/)

## effects

- containment is added only after a stable boundary is identified

### layered shadow

```css
:root {
  --shadow-md:
    0 1px 2px oklch(0% 0 0 / 0.08),
    0 4px 12px oklch(0% 0 0 / 0.06);
}
```

### deferred rendering

```css
.row {
  content-visibility: auto;
  contain-intrinsic-size: auto 12rem;
}
```
