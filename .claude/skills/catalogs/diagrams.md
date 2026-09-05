[agentic diagrams][agentic-diagrams]
    a free browser canvas for agent architectures, no signup
    plain language in, interactive animated diagram out
    24+ node types cover agents, tools, models, memory, routers, gateways
    edges type as request, response, async, streaming, event, or error
    named scenarios play back as animated step sequences
    export is png or json; json is the native format
    no text dsl, so diagrams are not git-diffable

[c4 agent skill][c4-agent-skill]
    a claude code and codex skill emits c4 diagrams via c4-plantuml
    output packs into an interactive html explorer for review
    covers context, container, component, deployment, and sequence views
    stamps outputs with timestamps and commit hashes
    published 2026-02-22 under the resilens open agent skills initiative

[code2uml][code2uml]
    agentic llm pipeline emits uml from code at repo scale
    importance-weighted compaction bridges codebase size and context windows
    compact payloads stay under 60kb per single diagram type

[mermaidseqbench][mermaidseqbench]
    132 nl-to-mermaid sequence diagram samples, llm-as-judge scoring
    axes are syntax, mermaid-only, logic, completeness, activation, errors
    first submitted 2025-11; v3 revised 2026-08-05

[canva sequence 2026][canva-sequence-2026]
    canva team tutorial dated 2026-07
    guidance covers participant limits, fragments, descriptive names, and detail control

[go uml sequence 2026][go-uml-sequence-2026]
    distributed systems and api guide dated 2026-04-07
    guidance covers scenario boundaries, triggers, outcomes, sync, async, and failures

[simplemermaid sequence 2026][simplemermaid-sequence-2026]
    microservice sequence tutorial dated 2026-03-12
    guidance covers participant order, message labels, error paths, notes, and co-location

[diagram code practice 2026][diagram-code-practice-2026]
    diagrams-as-code guide dated 2026-05-18
    guidance covers source co-location, freshness metadata, adrs, and ci rendering

[tool field 2026][tool-field-2026]
    mermaid leads on llm familiarity, render-everywhere, and pr review
    d2 wins on aesthetics and layout engines, mpl-2.0 plus paid platform
    the 2026 shift is mcp servers fronting excalidraw, tldraw, and mermaid
    code-first picks are mermaid or d2; canvas pick is excalidraw plus mcp

[excalidraw skill][excalidraw-skill]
    a skill gives any coding agent excalidraw diagram generation

[drawio mcp][drawio-mcp]
    mcp server lets agents emit drawio-compatible xml from source
    3.9k github stars as of 2026-05

[asciiflow][asciiflow]
    client-side browser canvas emits pure text boxes and arrows
    output stays grep-able, diffable, and screen-reader legible

[asciilogic][asciilogic]
    free in-browser ascii sketching of boxes, circles, lines, arrows
    exports to ascii, unicode, png, svg, or dxf

[graph easy][graph-easy]
    perl cli lays out graphs as ascii from a graphviz-like dsl

[diagon][diagon]
    text dsl to ascii for sequence, tree, table, flow, graph, and frames

[svgbob][svgbob]
    rust cli reads ascii scribbles and emits svg

[goat][goat]
    go cli renders ascii art into hand-drawn-style svg
    a go port of the markdeep.mini.js ascii diagram generator

[ascii agent skill][ascii-agent-skill]
    plan, draw, verify phases fix llm spatial drift in ascii diagrams
    draw allows only + - | > < ^ v / \ ; unicode box chars are banned
    grid.py places at 1-based columns; verify.py checks junctions and width
    default max width is 80 columns
    ships 10 examples: flowcharts, architectures, state machines, erds, nets
    10 stars as of 2026-08

[llm ascii limits][llm-ascii-limits]
    asciibench shows llms misread and misdraw visually-oriented text
    ascii art probes spatial reasoning that plain token streams hide

[typograms][typograms]
    a google-maintained definition and renderer for ascii diagram semantics
    primitives split into pipes, arrows, and connectors with combine rules
    media type is text/typogram
    trades expressivity and ergonomics for editability and portability

[svgbob spec][svgbob-spec]
    each character carries behaviors keyed to neighbor and direction
    . , ` ' round corners; + is a sharp junction; * o O are circles
    - | ~ _ : ! draw line styles; / \ draw 60 and 120 degree angles
    double quotes escape a run as literal text
    styling and tagged shapes sit outside the character spec

[ditaa syntax][ditaa-syntax]
    / and \ on corners render round; = dashes a row, : dashes a column
    one dash character spreads through the whole connected line
    cXXX hex and cRED-style names color shapes with auto text contrast
    {d} {s} {io} {o} {mo} {c} {tr} tags reshape a closed box
    o followed by text renders as a bullet

[ietf diagrams][ietf-diagrams]
    internet-draft ascii art stays under 72 columns for plaintext
    drafts ship svg and ascii twins; svg-only renders as a stub in text
    rfc 7996 constrains svg to monochrome, static, three font families
    aasvg bridges ascii to svg inside kramdown-rfc via aasvg fences

[aasvg][aasvg]
    a heavily modified markdeep parser turns ascii art into svg
    diagonals close polygons; markers at line ends become arrowheads
    arrow=solid default, arrow=line alternative; spaces tunes text merging
    bearcove/aasvg-rs ports it to rust with light and dark modes

[d2 plugin][d2-plugin]
    claude code plugin renders infra and architecture diagrams via d2
    /d2:diagram scans terraform, kubernetes, docker, and cloudformation
    emits d2 source, markdown docs, and light and dark svg
    5 subagents: scanner, enhancer, renderer, documenter, verifier
    requires the d2 cli; installs via claude plugin marketplace add
    anthropic marketplace submission #17401 closed as not planned
    readme claims mit but the repo has no license file
    15 stars, last pushed 2026-03-05

[d2 repo][d2-repo]
    org renamed terrastruct to d2lang; old urls redirect
    24.9k stars, mpl-2.0, pushed daily as of 2026-08
    v0.8.1 tagged 2026-08-07 with no release notes; v0.7.1 is last published
    native go ports of dagre, elk, sketch, latex land in v0.8
    dagre is 7-9x faster, elk 40-53x; elk 0.12 changes existing layouts
    txt output renders ascii since v0.7.1; --ascii-mode standard or extended
    validate, fmt --check, and stdin/stdout make the cli agent-drivable
    parser is hand-written recursive descent; no grammar artifact exists
    parse errors carry json ranges and return as a full slice
    no llms.txt, no ai docs, no official skill, plugin, or mcp server
    tala layout is proprietary: ~$240/yr, watermarked eval, ci needs enterprise
    ravsii/tree-sitter-d2 is the closest machine-readable grammar, third party

[d2 wasm][d2-wasm]
    official wasm package compiles and renders d2 with zero binary install
    layout options are dagre (default) and elk; elk runs slow under wasm
    latest is 0.1.33 from 2025-08; no publish in ~12 months

[d2 mcp servers][d2-mcp-servers]
    i2y/d2mcp: 10 tools, d2oracle incremental edits, embeds the go lib
    oracle create/set/delete/move/rename edits without full regeneration
    30 stars, most-starred d2 mcp, idle since 2025-07
    [h0rv][h0rv]
        validate-first: compile, render to png/svg/ascii, cheat-sheet tool
        19 stars, maintained as of 2026-04
    [wasm mcp][wasm-mcp]
        wasm-backed render/validate/inspect; only format needs the binary
        ships a bundled cross-agent d2 skill via npx skills add

[d2 skills][d2-skills]
    deepest d2 command surface: diagram, convert, architect, validate, render, config
    /d2-convert translates mermaid source to d2
    56-star marketplace repo, d2 plugin mit, pushed 2026-04
    [visual check][visual-check]
        only skill with a visual loop: render png, inspect, fix, 2-4 rounds
        detects and refuses watermarked tala output; falls back to elk
    [aws icons][aws-icons]
        pins 1480 terrastruct icons in a csv; never invents icon urls
    [hygiene][hygiene]
        best hygiene: dry-run install prompt, validate and fmt gates
        warns d2 writes partial renders on error, never trust file existence
    [ascii splice][ascii-splice]
        renders d2 to exact ascii and splices it into markdown via script
    [scoped][scoped]
        tightest permissions: allowed-tools bash scoped to d2 only
        ships a d2-vs-mermaid decision table; pushed 2026-08

[d2 ecosystem][d2-ecosystem]
    no d2 skill exceeds 20 stars; the field is small independent authors
    three cli-free paths: playground links, kroki http, wasm npm
    validation tiers: none, validate+fmt gates, visual self-inspection
    icon hallucination is the shared failure mode; pinned catalogs fix it
    top-traffic listing (jeremylongshore d2-diagram-creator) is boilerplate
    claudeskills.info diagram category indexes 158 skills, zero d2

## refs

[agentic-diagrams]: https://agenticdiagrams.com
[c4-agent-skill]: https://blog.heuel.org/2026/02/an-agentic-skill-for-interactive-c4-architecture-diagrams/
[code2uml]: https://arxiv.org/abs/2605.24453
[mermaidseqbench]: https://arxiv.org/abs/2511.14967
[canva-sequence-2026]: https://www.canva.com/online-whiteboard/sequence-diagram/
[go-uml-sequence-2026]: https://www.go-uml.com/best-practices-sequence-diagrams-distributed-systems-api/
[simplemermaid-sequence-2026]: https://simplemermaid.com/blog/sequence-diagram-tutorial-microservices.html
[diagram-code-practice-2026]: https://jamesm.blog/data-engineering/diagrams-as-code/
[tool-field-2026]: https://nimbalyst.com/blog/best-ai-diagram-tools-2026/
[excalidraw-skill]: https://github.com/coleam00/excalidraw-diagram-skill
[drawio-mcp]: https://github.com/jgraph/drawio-mcp
[asciiflow]: https://asciiflow.com
[asciilogic]: https://asciilogic.com
[graph-easy]: http://bloodgate.com/perl/graph/index.html
[diagon]: https://arthursonzogni.com/Diagon
[svgbob]: https://github.com/ivanceras/svgbob
[goat]: https://sw46.github.io/goat/
[ascii-agent-skill]: https://github.com/jasnell/opencode-skill-ascii-art-diagrams
[llm-ascii-limits]: https://arxiv.org/abs/2512.04125
[typograms]: https://google.github.io/typograms/
[svgbob-spec]: https://ivanceras.github.io/content/Svgbob/Specification.html
[ditaa-syntax]: https://github.com/stathissideris/ditaa
[ietf-diagrams]: https://authors.ietf.org/diagrams
[aasvg]: https://github.com/martinthomson/aasvg
[d2-plugin]: https://github.com/heathdutton/claude-d2-diagrams
[d2-repo]: https://github.com/d2lang/d2
[d2-wasm]: https://www.npmjs.com/package/@terrastruct/d2
[d2-mcp-servers]: https://github.com/i2y/d2mcp
[h0rv]: https://github.com/h0rv/d2-mcp
[wasm-mcp]: https://github.com/itsjool/d2-mcp
[d2-skills]: https://github.com/diegomarino/claude-toolshed
[visual-check]: https://github.com/khollingworth/d2-diagram-skill
[aws-icons]: https://github.com/junseinagao/d2-skill
[hygiene]: https://github.com/czyt/tinyskills
[ascii-splice]: https://github.com/UnBergant/d2-diagram-marketplace
[scoped]: https://github.com/laurigates/claude-plugins
[d2-ecosystem]: https://github.com/anthropics/claude-code/issues/17401
