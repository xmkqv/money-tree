---
name: Communicating Sequential Processes
short-name: CSP
kind: process-algebra
authors: C. A. R. Hoare; Stephen D. Brookes; A. W. Roscoe
notation: comparison abstraction
---

# communicating sequential processes

- a process is characterised through observable events and refusals [§§2–3][theory]
- process operators construct compound process behaviour [§§3–5][theory]
- concealment makes selected events unobservable [§5][theory]

```text:types
Process ::= STOP | Event -> Process | Process choice Process |
            Process parallel Process | Process hiding EventSet |
            recursive Variable.Process
```

# boundary and parallel composition

- a process alphabet states the events in which the process can engage [chapter 2][book]
- parallel processes synchronise on events shared by their alphabets [§2.3.3][book]

```text:surface
shared(P, Q) = alphabet(P) intersect alphabet(Q)
parallel(P, Q) synchronises every event in shared(P, Q)
hiding(P, H) removes H from observable events
```

# observation

- a trace is a finite sequence of events in which a process may engage [§2][theory]
- a failure pairs a trace with a finite set the process can refuse after that trace [§2][theory]
- divergence records unbounded internal activity [§4][semantics]

```text:types
Trace = Event*
Failure = <Trace, RefusalSet>
FailuresDivergences = <FailureSet, DivergenceSet>
```

# assurance

- refinement is set inclusion within a selected semantic model [§§3–4][semantics]
- compound-process denotations are constructed from component denotations [§§3–5][theory]

```text:surface
traceRefines(Q, P) iff traces(Q) subset traces(P)
fdRefines(Q, P) iff
    failures(Q) subset failures(P)
    and divergences(Q) subset divergences(P)
```

# refs

[book]: https://web.archive.org/web/20241230120713/http://www.usingcsp.com/cspbook.pdf
[theory]: https://doi.org/10.1145/828.833
[semantics]: https://www.cs.ox.ac.uk/people/bill.roscoe/publications/68b.pdf
