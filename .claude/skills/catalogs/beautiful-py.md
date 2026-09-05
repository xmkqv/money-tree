# beautiful-py

- window: 2026-02-13 through 2026-08-13
- source policy: current primary documentation and project releases
- baseline: python 3.14
- baseline: pydantic 2.13 stable

[python typing][python-typing]
    documentation updated 2026-08-13
    a type parameter expresses a relationship between two or more typed positions
    protocol expresses structural compatibility without nominal inheritance
    typeis narrows compatible input types in positive and negative branches
    paramspec preserves the parameter shape of a wrapped callable
    assert-never exposes an unhandled member of a closed union to a checker

[typing libraries][typing-libraries]
    guidance updated 2026-05-16
    input annotations accept the widest interface used by the implementation
    output annotations expose the concrete result when callers can rely on it
    reusable libraries test their public types with more than one checker when practical

[python data][python-data]
    documentation updated 2026-08-13
    a comprehension constructs a list, set, or dictionary from visible transforms and filters
    a complex traversal is clearer as a built-in operation or an explicit loop

[python functional][python-functional]
    documentation updated 2026-08-13
    a generator expression produces values on demand for a one-pass consumer
    an iterator can be consumed and does not promise repeated traversal
    unequal consumers of itertools tee can cause hidden buffering

[python dataclasses][python-dataclasses]
    documentation updated 2026-08-13
    a frozen slotted dataclass is a compact in-process value object
    post-init checks establish invariants after generated initialization
    unsafe-hash is unsuitable as a default

[python context][python-context]
    documentation updated 2026-08-13
    a context manager owns deterministic acquisition and release
    exit-stack owns a dynamic number of context managers

[python asyncio][python-asyncio]
    documentation updated 2026-08-13
    a task group owns related child tasks and waits for their completion
    the first non-cancellation failure cancels the remaining child tasks
    cancellation normally propagates after cleanup
    shield uncancel and eager task factories are exceptional tools

[python errors][python-errors]
    documentation updated 2026-08-13
    a domain exception derives from exception and adds useful context
    exception chaining preserves the lower-level cause
    a narrow try block prevents unrelated failures from being translated

[pep 798][pep-798]
    pep modified 2026-06-03
    starred comprehensions target python 3.15
    python 3.15 was not final during the research window
    starred comprehensions stay outside a python 3.14 guide

[pydantic boundaries][pydantic-boundaries]
    source updated 2026-07-21
    pydantic validates external or untrusted data at a trust boundary
    standard classes and dataclasses represent validated internal state
    repeated validation inside domain logic adds coupling and work

[pydantic config][pydantic-config]
    source updated 2026-07-20
    config-dict is the pydantic v2 configuration interface
    strictness unknown fields defaults assignments and revalidation are explicit policies
    configuration does not propagate through nested pydantic model boundaries

[pydantic fields][pydantic-fields]
    source updated 2026-04-15
    annotated composes reusable constraints while preserving the static base type
    assignment form supplies aliases and defaults to generated constructor signatures

[pydantic validators][pydantic-validators]
    source updated 2026-07-20
    an after validator receives the declared type
    a model after validator returns self after it checks cross-field invariants
    a validator returns its validated value
    assert is unsuitable for validation because optimized execution removes it

[pydantic models][pydantic-models]
    source updated 2026-08-08
    a generic model preserves relationships between fields
    a boundary explicitly parameterizes its generic model
    an unparameterized type variable can fall back to any or its bound
    model-construct skips validation and is not a default performance optimization

[pydantic adapter][pydantic-adapter]
    source updated 2026-08-08
    type-adapter validates a type expression without a wrapper model
    an adapter is reused because construction builds validators and serializers
    dump-json returns bytes

[pydantic unions][pydantic-unions]
    source updated 2026-08-08
    a discriminated union uses a literal tag on every stable variant
    a discriminator reduces ambiguous coercion validation work and error noise

[pydantic performance][pydantic-performance]
    source updated 2026-07-11
    model-validate-json avoids a separate json decode for json input
    concrete containers and discriminated unions reduce validation work
    performance changes follow measurement

[pydantic release][pydantic-release]
    release published 2026-05-06
    pydantic 2.13.4 was the latest stable release on 2026-08-13
    pydantic 2.14.0a1 was a prerelease and is excluded from stable guidance

[pyright config][pyright-config]
    source updated 2026-02-17
    python-version declares the analyzed runtime contract
    strict mode enables the complete strict diagnostic set

[mypy 2][mypy-2]
    release published 2026-05-06
    mypy 2.0 changed defaults for local partial types and byte distinctions
    checker behavior belongs to a versioned project contract

[ruff 016][ruff-016]
    release published 2026-07-23
    ruff 0.16 expanded its default rules and added markdown code formatting
    lint and format policy stays explicit and versioned

## refs

[python-typing]: https://docs.python.org/3/library/typing.html
[typing-libraries]: https://typing.python.org/en/latest/guides/libraries.html
[python-data]: https://docs.python.org/3.14/tutorial/datastructures.html
[python-functional]: https://docs.python.org/3.14/howto/functional.html
[python-dataclasses]: https://docs.python.org/3.14/library/dataclasses.html
[python-context]: https://docs.python.org/3.14/library/contextlib.html
[python-asyncio]: https://docs.python.org/3.14/library/asyncio-task.html
[python-errors]: https://docs.python.org/3.14/tutorial/errors.html
[pep-798]: https://peps.python.org/pep-0798/
[pydantic-boundaries]: https://github.com/pydantic/skills/blob/9deeebeea637be6e77b07afe98387fbc91e3511a/skills/pydantic/SKILL.md
[pydantic-config]: https://github.com/pydantic/pydantic/blob/dc484e21122131534fa4947886035d682082fc90/docs/concepts/config.md
[pydantic-fields]: https://github.com/pydantic/pydantic/blob/b36eaeb4e5eea176b5d638fce099c006564d02ad/docs/concepts/fields.md
[pydantic-validators]: https://github.com/pydantic/pydantic/blob/dc484e21122131534fa4947886035d682082fc90/docs/concepts/validators.md
[pydantic-models]: https://github.com/pydantic/pydantic/blob/9eb0444f71bb3e03da428758fd81d3d21c4060b4/docs/concepts/models.md
[pydantic-adapter]: https://github.com/pydantic/pydantic/blob/9eb0444f71bb3e03da428758fd81d3d21c4060b4/docs/concepts/type_adapter.md
[pydantic-unions]: https://github.com/pydantic/pydantic/blob/9eb0444f71bb3e03da428758fd81d3d21c4060b4/docs/concepts/unions.md
[pydantic-performance]: https://github.com/pydantic/pydantic/blob/f59e929c999e8b2efc7b12fd0bc1685c1a186be3/docs/concepts/performance.md
[pydantic-release]: https://github.com/pydantic/pydantic/releases/tag/v2.13.4
[pyright-config]: https://github.com/microsoft/pyright/blob/1bec65c15fba26016281d44d977bf667b89b9d30/docs/configuration.md
[mypy-2]: https://mypy-lang.blogspot.com/2026/05/mypy-20-relased.html
[ruff-016]: https://github.com/astral-sh/ruff/releases/tag/0.16.0
