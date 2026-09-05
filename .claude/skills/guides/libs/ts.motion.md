# ts motion

[ts](../code/ts.md)
[Motion JavaScript documentation](https://motion.dev/docs/animate)

- use stable `motion@^13.1.0`
- use `motion/mini` for element styles that the Web Animations API supports
- use `motion` for numbers, objects, CSS variables, independent transforms, SVG paths, sequences, and inertia
- treat every duration, delay, and playback-control time as seconds
- use an exact CDN version in a study; bundle or vendor the module graph when the result must be reproducible

## entry points

- use `onUpdate` only with a single-value animation

```ts
import { animate } from "motion/mini";

const element = document.querySelector<HTMLElement>("[data-panel]");
if (!element) throw new Error("panel is missing");

animate(
  element,
  {
    opacity: [0, 1],
    transform: ["translateY(8px)", "translateY(0px)"],
  },
  { duration: 0.2, ease: "easeOut" },
);
```

```ts
import { animate } from "motion";

declare const renderProgress: (progress: number) => void;

animate(0, 1, {
  duration: 0.56,
  ease: "linear",
  onUpdate: renderProgress,
});
```

## derived state

- derive values from motion values instead of reading animated CSS with `getComputedStyle()`
- use one explicit renderer when one progress value updates dense geometry
- use `mapValue`, `transformValue`, and effects when the dependency graph stays small
- remove effects and destroy manually created motion values when their owner is removed

```ts
import {
  animate,
  attrEffect,
  mapValue,
  motionValue,
  styleEffect,
  transformValue,
} from "motion";

declare const edgePath: (fold: number) => string;

const surface = document.querySelector<HTMLElement>("[data-surface]");
const edge = document.querySelector<SVGPathElement>("[data-edge]");
if (!surface || !edge) throw new Error("motion targets are missing");

const fold = motionValue(0);
const opacity = mapValue(fold, [0, 1], [0.35, 1]);
const d = transformValue(() => edgePath(fold.get()));

const stopSurface = styleEffect(surface, { "--fold": fold, opacity });
const stopEdge = attrEffect(edge, { d });
const controls = animate(fold, 1, { duration: 0.56, ease: "linear" });

export default () => {
  controls.stop();
  stopEdge();
  stopSurface();
  fold.destroy();
};
```

## interruption

Starting a new animation on the same motion value ends its active animation.
A physics spring reads that value and its current velocity.

- use a persistent motion value when interruption or velocity is part of the contract
- use a physics spring with `stiffness`, `damping`, and `mass` to inherit velocity
- do not expect a duration-based spring or `stop()` to provide velocity continuity

```ts
import { animate, motionValue, styleEffect } from "motion";

const panel = document.querySelector<HTMLElement>("[data-panel]");
if (!panel) throw new Error("panel is missing");

const x = motionValue(0);
const stopEffect = styleEffect(panel, { x });

export const settle = (target: number) =>
  animate(x, target, {
    type: "spring",
    stiffness: 320,
    damping: 34,
    mass: 0.8,
  });

export default () => {
  x.stop();
  stopEffect();
  x.destroy();
};
```

## clock and phase

Keep the clock linear when local phases apply their own easing. Compute the
maximum depth from the current data. This phase starts later values at a later
time and makes all values reach the target at global progress `1`.

```ts
import { cubicBezier } from "motion";

const ease = cubicBezier(0.3, 0, 0.12, 1);
const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

export default (
  progress: number,
  depth: number,
  maxDepth: number,
  lastStart: number,
) => {
  if (lastStart < 0 || lastStart >= 1) {
    throw new Error("lastStart must be at least 0 and less than 1");
  }
  const delay = maxDepth === 0 ? 0 : lastStart * depth / maxDepth;
  return ease(clamp01((progress - delay) / (1 - delay)));
};
```

## playback and scrubbing

- set `time` in seconds, not normalized progress
- pause a reusable animation before a gesture sets its time
- use `speed = -1` to play the same two-state timeline backwards
- use `pause()` when playback must resume; a stopped animation cannot restart

```ts
import { animate, motionValue } from "motion";

const fold = motionValue(0);
const timeline = animate(fold, [0, 1], {
  autoplay: false,
  duration: 0.56,
  ease: "linear",
});

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

export const scrub = (progress: number) => {
  timeline.pause();
  timeline.time = clamp01(progress) * timeline.duration;
};

export const settle = (target: 0 | 1) => {
  timeline.speed = target === 1 ? 1 : -1;
  timeline.play();
};
```

## svg

- hybrid Motion can interpolate `d` when both paths have matching commands and point order
- use a path mixer when the shapes do not match
- derive `d` from live geometry when endpoints follow values with different phases
- keep path elements mounted and update their attributes
- expect SVG path changes to cause paint

```ts
import { animate } from "motion";

const path = document.querySelector<SVGPathElement>("[data-edge]");
if (!path) throw new Error("edge is missing");

animate(
  path,
  {
    d: [
      "M 0 0 C 0 40 60 40 60 80",
      "M 0 0 C 30 0 30 80 60 80",
    ],
  },
  { duration: 0.4, ease: "easeInOut" },
);
```

## frame work

- group DOM reads before writes
- use `frame.read` and `frame.render` when custom work shares Motion's loop
- do not read computed style between per-element writes

```ts
import { frame } from "motion";

const element = document.querySelector<HTMLElement>("[data-source]");
const overlay = document.querySelector<HTMLElement>("[data-overlay]");
if (!element || !overlay) throw new Error("frame targets are missing");

frame.read(() => {
  const bounds = element.getBoundingClientRect();
  frame.render(() => {
    overlay.style.inlineSize = `${bounds.width}px`;
    overlay.style.blockSize = `${bounds.height}px`;
  });
});
```

## view changes

- use `animateView` for snapshot-based DOM layout changes
- do not use it when the intermediate state must stay live and interactive
- keep native scrolling, content extent, and scroll-position handoff in DOM code
- use Motion for the clock only when geometry remains application state
