# [typst][typst:docs]

## template via everything-show

```typ
// template.typ
#let template(title: none, authors: (), body) = {
  set document(title: title, author: authors.map(a => a.name))
  set page(paper: "a4", margin: (x: 2.5cm, y: 2cm), numbering: "1")
  set text(font: ("Libertinus Serif", "Noto Sans"), size: 11pt, lang: "en")
  set par(justify: true, leading: 0.65em)
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => block(above: 2em, below: 1em, it)
  body
}

// main.typ
#import "template.typ": template
#show: template.with(title: [Title], authors: ((name: "Name"),))
```

## context header and footer

```typ
#set page(
  header: context {
    if counter(page).get().first() == 1 { return }
    let before = query(selector(heading.where(level: 1)).before(here()))
    let current = if before.len() > 0 { before.last().body } else { none }
    emph(current); h(1fr); counter(page).display()
  },
  footer: context align(center)[
    #counter(page).display("1 / 1", both: true)
  ],
)
```

## selector-scoped show rules

```typ
#show figure.where(kind: table): set figure.caption(position: top)
#show table.cell.where(y: 0): strong
#show raw.where(block: true): it => block(
  width: 100%, fill: luma(245), inset: 8pt, radius: 4pt, it,
)
#show link: underline
#show ref: it => text(fill: blue, it)
```

## table with repeating header and spans

```typ
#set table(
  stroke: (x, y) => if y == 0 { (bottom: 0.7pt) },
  align: (x, y) => if x > 0 { right } else { left },
)
#table(
  columns: (2fr, 1fr, 1fr),
  table.header(
    table.cell(rowspan: 2)[*Item*], table.cell(colspan: 2)[*Range*],
    [*min*], [*max*],
  ),
  ..rows.map(r => (r.name, str(r.min), str(r.max))).flatten(),
)
```

## counters, state, and cross-location queries

```typ
#let step = counter("step")
#let mark(body) = [#step.step() #context step.display() #body <step>]

#context {
  let all = query(<step>)
  for s in all [ #step.at(s.location()).first() on page #s.location().page() ]
}
```

## citations and bibliography

```typ
#set cite(style: "chicago-author-date")
Prior work @key1[p. 42] and @key2.
#cite(<key3>, form: "prose") argues otherwise.
#bibliography("refs.bib", style: "ieee", title: [References])
```

## external inputs and data

```typ
#let inputs = sys.inputs
#let env = inputs.at("env", default: "dev")
#let data = json.decode(inputs.at("payload", default: "{}"))
#let rows = csv("data.csv", row-type: dictionary)
#let cfg = yaml("config.yaml")
```

```sh
typst compile --input env=prod --input payload="$(cat data.json)" main.typ
```

## markdown rendered inside typst

```typ
#import "@preview/cmarker:0.1.10"
#import "@preview/mitex:0.2.7": mitex
#cmarker.render(
  read("doc.md"),
  math: mitex,
  h1-level: 0,
  scope: (image: (source, ..args) => figure(image(source, ..args))),
)
```

## pandoc to typst

```sh
pandoc doc.md --pdf-engine=typst -V mainfont="Inter" -V papersize=a4 \
  -V margin.x=2cm -V margin.y=2.5cm -V linestretch=1.2 -o doc.pdf
pandoc doc.md -t typst --template=my.typ -o doc.typ    # inspect emitted code
pandoc --print-default-template=typst > default.typ    # baseline to customize
```

## cli

```sh
typst init @preview/some-template:1.0.0 project
typst watch --root . --font-path ./fonts main.typ out.pdf
typst compile --pdf-standard a-2b,ua-1 main.typ
typst compile --features html main.typ main.html
typst query main.typ "<step>" --field value --one
typst fonts
```

## refs

[typst:docs]: https://typst.app/docs/
    Pure functions; a `set` rule inside `[…]`/`{…}` scopes only to that block

[typst:styling]: https://typst.app/docs/reference/styling/
    `show fn: it => …` recurses into children; guard or use show-set to avoid loops

[typst:context]: https://typst.app/docs/reference/context/
    `counter.get()`, `state.get()`, `here()`, `measure()` all require `context`

[typst:changelog]: https://typst.app/docs/changelog/
    `locate(fn)`, `style`, `state.display()` removed; `pdf.embed` → `pdf.attach`

[typst:page]: https://typst.app/docs/guides/page-setup/
    Header and footer are `context` closures; header evaluates before body

[typst:text]: https://typst.app/docs/reference/text/text/
    `font:` array is a fallback chain; missing fonts fall back silently

[typst:table]: https://typst.app/docs/guides/tables/
    `table.header` repeats across pages; spanning cells may ignore `set table`

[typst:cite]: https://typst.app/docs/reference/model/cite/
    `style:` takes a built-in CSL name or a `.csl` path

[typst:sys]: https://typst.app/docs/reference/foundations/sys/
    `sys.inputs` values are always strings; parse with `json.decode`

[typst:cli]: https://typst.app/docs/reference/introspection/query/
    `--root` must contain the main file; paths may not contain backslashes

[typst:pdf]: https://typst.app/docs/reference/pdf/
    `--pdf-standard a-2a,ua-1` combines PDF/A and tagged PDF/UA-1

[typst:packages]: https://typst.app/universe/
    `@preview/name:version` requires an exact version; no latest alias

[cmarker:docs]: https://github.com/SabrinaJewson/cmarker.typ
    `math: none` skips math entirely; supply `mitex`; `h1-level` default is 1

[pandoc:typst]: https://pandoc.org/MANUAL.html#variables-for-typst
    `thanks` is broken as of typst 0.15; prefer `-V template=x.typ` over `$vars$`

[tinymist:docs]: https://myriad-dreamin.github.io/tinymist/
    LSP with live preview; set root path manually for multi-file projects
