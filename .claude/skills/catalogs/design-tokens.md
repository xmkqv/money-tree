[design md][design-md]
    `design.md` is a single-file representation of a visual design system
    yaml front matter stores machine-readable design tokens
    markdown sections store design rationale and usage guidance
    token groups cover colors, typography, rounded corners, spacing, and components
    component entries map component property names to literals or token references
    the repository supplies complete example files

[ds0 yaml manifests][ds0-yaml-manifests]
    ds0 stores one yaml manifest per component
    a manifest can declare selection guidance, variants, props, a decision tree, accessibility, relations, composition examples, token usage, and a storybook path
    separate yaml files describe multi-component patterns and category decision trees
    the repository contains 95 component manifests
    the published json schema does not match the current manifest shape
    current manifests therefore require schema repair before strict reuse

[terrazzo yaml tokens][terrazzo-yaml-tokens]
    terrazzo accepts json, jsonc, and yaml token sources
    terrazzo interprets yaml token data with dtcg token semantics
    terrazzo supports multiple source files and deterministic merge order
    the cli includes yaml support
    the lower-level parser requires a separate yaml adapter
    [terrazzo token types][terrazzo-token-types]
        the token reference supplies yaml examples for supported token types

[welcome component yaml][welcome-component-yaml]
    welcome extracts figma components into yaml component data
    `props` stores normalized component properties
    `anatomy` stores component structure and default slot content
    slot properties record cardinality, openness, preferred values, empty display, and stretching
    figma-specific source data is preserved under a vendor extension
    the public documentation contains excerpts but the full component data is private

[dsds][dsds]
    the design system doc spec defines a machine-readable documentation metamodel
    entities include components, tokens, token groups, themes, foundations, patterns, guides, and chunks
    typed document blocks cover anatomy, api, variants, states, accessibility, design specifications, guidance, and interactions
    the normative instances and examples use json rather than yaml
    the specification composes with dtcg token files instead of duplicating token values

[spectrum design data][spectrum-design-data]
    spectrum design data defines a formal component contract
    a component can declare identity, options, slots, anatomy, states, lifecycle, token bindings, document blocks, and accessibility
    semantic rules validate token references against declared component variants, anatomy, and states
    component declarations and token datasets use json files
    the layer-two validation catalog uses yaml

[deepgram design system yaml][deepgram-design-system-yaml]
    deepgram publishes a production design-system source in yaml
    the model includes tokens, base styles, utilities, navigation categories, components, variants, recursive parts, and example syntax trees
    its json schema requires a version, tokens, categories, and components
    the source is a complete reference rather than a blank starter
    [deepgram design system schema][deepgram-design-system-schema]
        the schema validates the published yaml model

[brandspec yaml][brandspec-yaml]
    brandspec supplies a reusable standalone yaml template
    the model includes brand identity, voice, dtcg-shaped tokens, assets, guidelines, lint rules, and extensions
    a yaml json schema and a complete example accompany the starter
    [brandspec yaml schema][brandspec-yaml-schema]
        the schema validates brandspec documents

[open codesign template][open-codesign-template]
    open codesign supplies a filled design.md scaffold with replaceable project identity
    the yaml front matter covers colors, typography, radii, spacing, and components
    the file follows the google design.md representation

[hue design model][hue-design-model]
    hue supplies an inline design-model.yaml scaffold
    the model covers primitives, semantic tokens, components, motion, elevation, compositions, iconography, and screen rules
    the repository supplies multiple complete design-model examples
    the scaffold is broad but has no published validation schema

[craft token template][craft-token-template]
    craft supplies a conventional tokens.yaml starter
    placeholders define brand colors
    defaults define spacing, radii, typography, shadows, motion, stack order, and breakpoints

[hrdt yaml][hrdt-yaml]
    human-readable design tokens define a compact yaml token format
    the model separates primitive, semantic, and component token layers
    the tool validates the yaml and converts it to dtcg json and platform outputs
    [hrdt schema][hrdt-schema]
        the json schema validates hrdt token documents

[red hat yaml tokens][red-hat-yaml-tokens]
    red hat maintains production token sources in yaml
    the files use dtcg-shaped types, values, descriptions, aliases, extensions, deprecation, and theme-aware values
    the source is a reference set rather than a reusable blank template

## refs

[design-md]: https://github.com/google-labs-code/design.md/blob/main/docs/spec.md
[ds0-yaml-manifests]: https://github.com/rwyatt2/ds0/tree/main/packages/ai/manifests
[terrazzo-yaml-tokens]: https://terrazzo.app/docs/reference/config/
[terrazzo-token-types]: https://terrazzo.app/docs/reference/tokens/
[welcome-component-yaml]: https://design.accor.com/latest/terminology/slots-in-figma-thVKJup6
[dsds]: https://designsystemdocspec.org/
[spectrum-design-data]: https://opensource.adobe.com/spectrum-design-data/spec/component-format/
[deepgram-design-system-yaml]: https://unpkg.com/@deepgram/styles@0.2.15/design-system.yaml
[deepgram-design-system-schema]: https://design.dx.deepgram.com/.well-known/design-system-schema-v1.json
[brandspec-yaml]: https://github.com/brandspec/brandspec/blob/main/workshop/templates/brand.yaml
[brandspec-yaml-schema]: https://github.com/brandspec/brandspec/blob/main/schema/v0.1.0.yaml
[open-codesign-template]: https://github.com/OpenCoworkAI/open-codesign/blob/3198d492c76241f0cfd1ba5d2fb3eb06283c204a/apps/desktop/resources/templates/scaffolds/design-systems/DESIGN.md
[hue-design-model]: https://github.com/dominikmartn/hue/blob/8cd185f927e0a23889e28cb5bf9f366e51e35309/SKILL.md#L294-L522
[craft-token-template]: https://github.com/drobins25/craft/blob/b1e33a88ece2d0ca8161a7870d7fef62acd9f704/templates/craft/design/tokens.yaml
[hrdt-yaml]: https://github.com/design-token-kit/design-token-kit/blob/main/examples/tokens/valid.hrdt.yaml
[hrdt-schema]: https://github.com/design-token-kit/design-token-kit/blob/main/core/src/core/validation/hrdt/schemas/hrdt-tokens.json
[red-hat-yaml-tokens]: https://github.com/RedHat-UX/red-hat-design-tokens/tree/main/tokens
