# motion

## value animation

```ts
import { animate } from "motion"
controls = animate(0, 1, { duration: 0.5, ease: "linear", onUpdate: render })
```

## derived effects

```ts
import { motionValue, mapValue, styleEffect } from "motion"
progress = motionValue(0)
opacity = mapValue(progress, [0, 1], [0.2, 1])
stopEffect = styleEffect(element, { opacity })
controls = animate(progress, 1, { duration: 0.5 })
onDispose(() => {
    controls.stop()
    stopEffect()
    opacity.destroy()
    progress.destroy()
})
```

## interruptible spring

```ts
position = motionValue(0)
settle = target => animate(position, target, {
    type: "spring", stiffness: 320, damping: 34, mass: 0.8,
})
```

## scrubbing and reversal

```ts
timeline = animate(progress, [0, 1], { autoplay: false, duration: 0.5, ease: "linear" })
scrub = fraction => {
    timeline.pause()
    timeline.time = Math.min(1, Math.max(0, fraction)) * timeline.duration
}
resume = direction => {
    timeline.speed = direction
    timeline.play()
}
```

## compatible svg paths

```ts
animate(path, { d: [
    "M 0 0 C 0 40 60 40 60 80",
    "M 0 0 C 30 0 30 80 60 80",
] }, { duration: 0.4, ease: "easeInOut" })
```

## scheduled geometry

```ts
import { frame } from "motion"
frame.read(() => {
    bounds = element.getBoundingClientRect()
    frame.render(() => overlay.style.inlineSize = `${bounds.width}px`)
})
```

## tips

- [animation][animate] durations and playback times are seconds.
- physics springs inherit velocity from a persistent motion value.
- `pause()` preserves resumable playback; `stop()` ends the animation.
- matching svg path commands and point order permit direct interpolation.
- `motion/mini` covers native element styles; `motion` also supports values and sequences.

## refs

[animate]: https://motion.dev/docs/animate
