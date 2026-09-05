[rfc 3986][rfc-3986]
    rfc 3986 defines the generic syntax of uri references
    the generic components are scheme, authority, path, query, and fragment
    it defines uri, relative-reference, path, query, and generic fragment productions
    it defines reference resolution, recomposition, normalization, and comparison
    its grammar is a superset for parsing and is not a generative grammar for every uri scheme
    it does not define a source-span fragment
    fragment semantics depend on the representation media type
    it does not impose one canonical lexical form on fragment content

[rfc 5147][rfc-5147]
    rfc 5147 updates the text/plain media type with fragment identifier syntax and processing
    it does not define a complete uri, uri path, uri scheme, or relative-reference grammar
    rfc 5147 defines text/plain line and character positions and ranges
    the fragment grammar starts with `char=` or `line=` and can add `length=` or `md5=` integrity checks
    `line=10,20` selects line positions 10 through 20 and therefore human lines 11 through 20
    `char=100,140` selects character positions 100 through 140
    positions are zero based and ranges are end exclusive
    scheme names are exact lower-case text
    the full syntax permits one position, open ranges, leading zeroes, and optional length or md5 integrity checks
    it has no line-and-column range form
    it does not define a canonical lexical form because different accepted strings can select the same span

[rfc 6838][rfc-6838]
    media type registrations can specify how applications interpret fragment identifiers
    media types are encouraged to adopt fragment schemes from semantically similar media types
    no fragment interpretation automatically applies to all text or source-code media types

[rfc 8820][rfc-8820]
    uri specifications must not impose fragment structure across media types
    reusable fragment syntax requires adoption by the applicable media types

[rfc 9239][rfc-9239]
    the javascript media type registration does not define fragment resolution
    javascript source therefore does not automatically use rfc 5147

[w3c annotation][w3c-annotation]
    the web annotation recommendation models a source and a selector separately
    its fragment selector can declare conformance to rfc 5147
    it recommends a fragment selector over placing the fragment directly in the iri
    the source, a hash, and the selector value can reconstruct the fragment iri

[w3c selectors states][w3c-selectors-states]
    the working group note defines `source#selector(type=TextPositionSelector,start=412,end=795)`
    the document is a note and does not imply w3c endorsement
    the note says the fragment syntax needs registration for each media type
    it warns that the syntax can conflict with registered media-type fragments
    it recommends this single-iri mapping only when the full structured representation cannot be managed
    parameter order and encoding choices do not give the mapping one canonical lexical form

[w3c text position][w3c-text-position]
    the w3c recommendation models a source and a text position selector separately
    start is zero based and inclusive and end is exclusive
    the structured model is applicable across several text-bearing media types

[sarif][sarif]
    sarif models source analysis locations as an artifact uri plus a separate region
    regions support line and column bounds, character offsets and lengths, and byte offsets and lengths
    line and column numbers are one based
    end columns are exclusive

[lsp location][lsp-location]
    language server protocol locations contain a document uri and a separate range
    ranges contain zero-based line-and-character start and end positions
    the end position is exclusive

[scip range][scip-range]
    scip documents contain relative paths
    occurrences contain separate half-open source ranges
    ranges can encode single-line or multi-line line-and-character bounds

[github code links][github-code-links]
    github supports links to one line or an inclusive range of lines
    stable links include a commit revision
    the line fragment is a github convention rather than a general uri standard

[vscode uri][vscode-uri]
    vscode accepts a uri fragment such as `L3,5` for one line and column position in `text/uri-list`
    vscode represents a full source range as a separate `Location` or `Range` object
    the fragment syntax is a vscode convention rather than a general uri standard

[text fragments][text-fragments]
    url text fragments select text by content with `:~:text=`
    start and end terms can define a range that is more resistant to shifted lines
    the document is a community group report and not a w3c standard
    the form targets browser-visible html or plain text and is unsuitable as a compact source-coordinate key

[epub cfi][epub-cfi]
    epub canonical fragment identifiers define `book.epub#epubcfi(...)`
    epub cfi supports structural paths, character offsets, and ranges
    the specification is deliberately restricted to epub publications
    its existence does not provide a canonical fragment for arbitrary files

## refs

[rfc-3986]: https://www.rfc-editor.org/rfc/rfc3986.html
[rfc-5147]: https://www.rfc-editor.org/rfc/rfc5147.html
[rfc-6838]: https://www.rfc-editor.org/rfc/rfc6838.html#section-4.11
[rfc-8820]: https://www.rfc-editor.org/rfc/rfc8820.html#section-2.5
[rfc-9239]: https://www.rfc-editor.org/rfc/rfc9239.html#section-2
[w3c-annotation]: https://www.w3.org/TR/annotation-model/#fragment-selector
[w3c-selectors-states]: https://www.w3.org/TR/selectors-states/#selectors-and-states-as-fragment-identifiers
[w3c-text-position]: https://www.w3.org/TR/annotation-model/#text-position-selector
[sarif]: https://docs.oasis-open.org/sarif/sarif/v2.1.0/os/sarif-v2.1.0-os.html
[lsp-location]: https://github.com/microsoft/language-server-protocol/blob/gh-pages/_specifications/lsp/3.18/types/location.md
[scip-range]: https://github.com/scip-code/scip/blob/main/scip.proto
[github-code-links]: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-a-permanent-link-to-a-code-snippet
[vscode-uri]: https://code.visualstudio.com/api/references/vscode-api
[text-fragments]: https://wicg.github.io/scroll-to-text-fragment/
[epub-cfi]: https://w3c.github.io/epub-specs/epub33/epubcfi/
