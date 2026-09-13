---
name: humanizer
description: only-if-asked
license: MIT
metadata:
  version: "2.11.2"
---

# Humanizer: remove AI writing patterns

Rewrite AI-sounding text so it reads like the writer, not a chatbot. Do not change what it says or make up details.

These patterns come from WikiProject AI Cleanup's [Signs of AI writing][source] on Wikipedia.

## What to do

When given text to humanize:

1. **Find AI patterns.** Check the text against the patterns below.
2. **Keep every claim.** Adjust length and paragraph structure as needed without losing information.
3. **Ground facts in input.** Ask or omit missing details. Fiction and fitting opinions may be original; facts may not.
4. **Match the voice.** Match the text's tone; add personality only where it suits both the text and the writer.

Apply the same process in every mode; choose output using [How to return the result](#how-to-return-the-result).

## Match the writer's voice

If the user provides a writing sample (their own previous writing), analyze it before rewriting:

1. Note the sample's sentence lengths, vocabulary, openings, punctuation, repeated phrases, and transitions.
2. Match those habits. Do not replace casual words with formal ones or remove deliberate quirks.
3. If there is no sample, use the guidance below.

The sample overrides these rules, including §14: match its em dash frequency instead of banning them.

## Add personality only when it fits

Removing AI patterns is only half the job. The result should still sound like a person.

Use fitting personality in personal or opinion writing; keep reference, technical, legal, and factual text neutral.

Preserve fitting opinions, doubts, mixed feelings, humor, asides, and uneven rhythm without inventing facts.

## Content patterns

### 1. Inflated claims about importance and legacy

**Watch:** claims of pivotal roles, historic shifts, lasting legacies, broader significance, or deep roots.
**Problem:** Ordinary details are inflated into historic changes, legacies, or broad trends.
**Before:**
> Catalonia founded its statistics institute in 1989, marking a pivotal turn in Spain's decentralization.
**After:**
> Catalonia founded its statistics institute in 1989 as part of Spain's administrative decentralization.

### 2. Name-dropping to prove importance

**Watch:** prestige citations, regional or national coverage, leading experts, and follower counts without context.
**Problem:** Publication names or follower counts often serve as empty proof of importance.
**Before:**
> The New York Times, BBC, Financial Times, and The Hindu cite her views; she boasts over 500,000 followers.
**After:**
> The New York Times, BBC, Financial Times, and The Hindu cite her views. She has over 500,000 followers.

Keep sourced details about what someone said and where. Never invent context to shorten a citation.

### 3. Shallow analysis with -ing phrases

**Watch:** -ing clauses that highlight, ensure, symbolize, contribute, foster, encompass, or showcase.
**Problem:** AI writing often adds an -ing phrase to make a simple fact sound deeper than it is.
**Before:**
> The temple's blue, green, and gold evoke Texas bluebonnets and the Gulf, reflecting a deep bond with the land.
**After:**
> The temple is painted blue, green, and gold, colors meant to evoke Texas bluebonnets and the Gulf of Mexico.

### 4. Sales language

**Watch:** boasts, vibrant, rich, profound, renowned, nestled, breathtaking, must-visit, and figurative groundbreaking.
**Problem:** Descriptions of places, cultures, products, or organizations often become advertisements.
**Before:**
> Nestled in Ethiopia's breathtaking Gonder region, Alamata Raya Kobo boasts rich heritage and stunning beauty.
**After:**
> Alamata Raya Kobo is a town in the Gonder region of Ethiopia.

### 5. Vague sources

**Watch:** unnamed experts, observers, critics, or industry reports; plural sources when few are cited.
**Problem:** AI writing often assigns a claim to unnamed experts, critics, reports, or observers.
**Before:**
> Experts call the unusual Haolai River vital to the ecosystem; researchers and conservationists study it.
**After:**
> Researchers and conservationists study the Haolai River for its unusual characteristics.

Name a real source when the source text provides one. Otherwise, remove the unsupported claim. Never invent a source.

### 6. Formulaic challenges and outlook sections

**Watch:** Despite these challenges, Challenges and Legacy, Future Outlook, and stock lists of obstacles.
**Problem:** Stock challenges or outlook sections repeat vague claims about obstacles and growth without adding facts.
**Before:**
> Despite traffic congestion and water shortages, Korattur continues to thrive as part of Chennai's growth.
**After:**
> Korattur has recurring traffic congestion and water shortages.

Add details such as dates or public actions only when they come from the source or the user.

## Language and grammar patterns

### 7. Overused AI words

**Watch:** delve, garner, pivotal, quietly, vibrant, tapestry, figurative gate/gated/gating; preserve technical uses.
**Problem:** AI writing uses these words much more often than most people do, especially in groups.
**Before:**
> Camel meat is a distinctive Somali delicacy; pasta's enduring presence in the south is a testament to Italian rule.
**After:**
> Camel meat is a Somali delicacy. Pasta, introduced under Italian rule, remains common, especially in the south.

### 8. Avoiding is and are

**Words to watch:** serves as/stands as/marks/represents [a], boasts/features/offers [a]
**Problem:** AI writing often replaces simple verbs such as *is*, *are*, and *has* with longer phrases.
**Before:**
> Gallery 825 serves as LAAA's contemporary art space, boasting four rooms totaling over 3,000 square feet.
**After:**
> Gallery 825 is LAAA's contemporary art space. It has four rooms totaling over 3,000 square feet.

### 9. Not X but Y and clipped negative endings
**Problem:** AI writing overuses forms such as "Not only...but..." and "It's not just X, it's Y."

It also adds clipped endings such as "no guessing" instead of writing a clear clause.
**Before:**
> It's not just a heavy beat; it's aggression and atmosphere. It's not merely a song, it's a statement.
**After:**
> The heavy beat adds to the aggressive tone.
**Before (tailing negation):**
> The options come from the selected item, no guessing.
**After:**
> The options come from the selected item without forcing the user to guess.

### 10. Forced groups of three
**Problem:** AI writing often forces ideas into groups of three to sound complete.
**Before:**
> Talks, panels, and networking await. Expect innovation, inspiration, and industry insights.
**After:**
> The event includes talks and panels. There's also time for informal networking between sessions.

### 11. Changing names and repeating sentence openings
**Problem:** AI prose cycles through names for one subject or repeats the same opening, often *she* or *he*.

Keep one name per subject. Vary repeated openings by merging sentences, changing the subject, or leading with action.
**Before (synonym cycling):**
> The protagonist faces challenges. The main character overcomes them. The central figure wins. The hero returns home.
**After:**
> The protagonist faces many challenges but eventually triumphs and returns home.
**Before (repeated openings):**
> She noted the door. She noted the lock on it. She filed both away.
**After:**
> She noted the door and its lock, then filed both away.

Do not ban the repeated word. Fix the repeated sentence pattern. The remaining sentence may still start with "She."

### 12. False from X to Y ranges
**Problem:** AI writing often uses "from X to Y" when X and Y do not form a real range.
**Before:**
> We journey from the Big Bang to the cosmic web, from stars' birth and death to dark matter's enigmatic dance.
**After:**
> The book covers the Big Bang, star formation, and current theories about dark matter.

### 13. Passive voice and missing subjects
**Problem:** Hidden actors and missing subjects obscure meaning. Use active voice when it clarifies who does what.
**Before:**
> No configuration file needed. The results are preserved automatically.
**After:**
> You do not need a configuration file. The system preserves the results automatically.

## Style patterns

### 14. Em and en dashes

**Rule:** Unless the sample uses dashes, replace `—`, `–`, ` — `, and ` -- ` with punctuation or rephrase.
**Before:**
> Dutch institutions—not the people—promote this label. Even official addresses say "Netherlands, Europe"—a misnomer.
**After:**
> Dutch institutions, not the people, promote this label. Even official addresses say "Netherlands, Europe", a misnomer.
**Before:**
> The policy — unannounced — affects thousands. The changes -- overdue, critics say -- take effect immediately.
**After:**
> The unannounced policy affects thousands. The changes, overdue according to critics, take effect immediately.

Before returning, search for `—` and `–`; remove them unless the sample uses them, then match its frequency.

### 15. Too much bold text
**Problem:** AI chatbots often bold words and phrases without a clear reason.
**Before:**
> It blends **OKRs**, **KPIs**, the **Business Model Canvas**, and the **Balanced Scorecard** for visual strategy.
**After:**
> It blends OKRs, KPIs, and visual strategy tools like the Business Model Canvas and Balanced Scorecard.

### 16. Lists with bold mini-headings
**Problem:** AI writing often uses vertical lists in which every item starts with a bold label and a colon.
**Before:**
> - **User Experience:** The user experience has been significantly improved with a new interface.
> - **Performance:** Performance has been enhanced through optimized algorithms.
> - **Security:** Security has been strengthened with end-to-end encryption.
**After:**
> The update improves the interface, speeds up load times through optimized algorithms, and adds end-to-end encryption.

### 17. Title case in headings
**Problem:** AI chatbots often capitalize every main word in a heading.
**Before:**
> ## Strategic Negotiations And Global Partnerships
**After:**
> ## Strategic negotiations and global partnerships

### 18. Emojis
**Problem:** AI chatbots often add emojis to headings and list items as decoration.
**Before:**
> 🚀 **Launch Phase:** The product launches in Q3
> 💡 **Key Insight:** Users prefer simplicity
> ✅ **Next Steps:** Schedule follow-up meeting
**After:**
> The product launches in Q3. User research showed a preference for simplicity. Next step: schedule a follow-up meeting.

### 19. Curly quotation marks
**Problem:** ChatGPT often uses curly quotes (“...”) where the writer or target format uses straight quotes ("...").
**Before:**
> He said “the project is on track” but others disagreed.
**After:**
> He said "the project is on track" but others disagreed.

## Chatbot patterns

### 20. Chatbot text left in the answer

**Watch:** greetings, praise, offers to expand, requests for feedback, and closings such as I hope this helps.
**Problem:** A chatbot's greeting, offer, or closing sometimes remains in text that should stand on its own.
**Before:**
> Here is an overview of the French Revolution. I hope this helps! Let me know if you'd like more detail.
**After:**
> The French Revolution began in 1789 when financial crisis and food shortages led to widespread unrest.

### 21. Knowledge-limit disclaimers and guesses

**Watch:** training cutoffs, scarce-information disclaimers, assumed privacy, and guesses about undocumented events.
**Problem:** Models cite knowledge gaps, then guess. State the source's limits or omit the claim; never assert a guess.
**Before (cutoff disclaimer):**
> Though founding details are scarce in available sources, the company appears to date from the 1990s.
**After:**
> Available sources give no founding date. (Or omit this; state a date only when sourced.)
**Before (speculative gap-fill):**
> Her undocumented early life suggests privacy. A likely middle-class upbringing shaped her education reform work.
**After:**
> Her early life is not documented in the available sources. (Or omit the section.)

### 22. Overly agreeable tone
**Problem:** AI assistants often praise the user or agree before giving the answer.
**Before:**
> Great question! You're right that this is complex. Excellent point about the economic factors!
**After:**
> The economic factors you mentioned are relevant here.

## Filler and hedging

### 23. Filler phrases

**Before → After:**
- "In order to achieve this goal" → "To achieve this"
- "Due to the fact that it was raining" → "Because it was raining"
- "At this point in time" → "Now"
- "In the event that you need help" → "If you need help"
- "The system has the ability to process" → "The system can process"
- "It is important to note that the data shows" → "The data shows"

### 24. Too many qualifiers

**Watch:** stacked qualifiers such as could potentially, might arguably, and in some cases it may.
**Problem:** Edits can stack hedges. Keep only sourced, necessary qualifiers; remove caveats masking overstatements.
**Before:**
> It could potentially possibly be argued that the policy might have some effect on outcomes.
**After:**
> The policy may affect outcomes.

### 25. Generic positive endings
**Problem:** AI writing often ends with vague optimism instead of the last useful fact.
**Before:**
> A bright future awaits the company. Exciting times lie ahead on its journey toward excellence and progress.
**After:**
> (Cut the paragraph. End on the last concrete fact instead of a send-off. If the source states real plans, use those.)

### 26. Too many hyphenated word pairs

**Watch:** repeated hyphenation of third-party, cross-functional, data-driven, high-quality, real-time, and long-term.
**Problem:** Hyphenation is overused. Write `a high-quality report` before a noun, but `the report is high quality`.
**Before:**
> The cross-functional team wrote a high-quality, data-driven report. The report is high-quality and data-driven.
**After:**
> The cross-functional team wrote a high-quality, data-driven report. The report is high quality and data driven.

### 27. Pretending to reveal a deeper truth

**Watch:** The real question is, at its core, in reality, fundamentally, the deeper issue, and the heart of the matter.
**Problem:** AI writing uses these phrases to make an ordinary point sound like a hidden truth.
**Before:**
> The real question is whether teams can adapt. At its core, what really matters is organizational readiness.
**After:**
> Teams' ability to adapt largely depends on their readiness to change their habits.

### 28. Announcing the next point

**Watch:** Let's dive in, let's explore, here's what you need to know, heads up, quick note, and before I forget.
**Problem:** Formal or casual announcements delay the point. Remove the preamble, including one thing that bit me.
**Before:**
> Let's dive into how caching works in Next.js. Here's what you need to know.
**After:**
> Next.js caches data at multiple layers, including request memoization, the data cache, and the router cache.
**Before (casual register):**
> One thing that bit me, so pay attention: the webpack dev server doesn't send the CORS header by default.
**After:**
> The webpack dev server doesn't send the CORS header by default.

### 29. A heading repeated in the first sentence

**Watch:** A heading followed by a one-line restatement before the content begins.
**Problem:** Opening sentences often repeat their headings. Remove the repetition.
**Before:**
> ## Performance
>
> Speed matters.
>
> When users hit a slow page, they leave.
**After:**
> ## Performance
>
> When users hit a slow page, they leave.

### 30. Writing about the previous version
**Problem:** Describe current behavior; reserve prior versions for documents about change, such as release notes.
**Before:**
> This function replaced the old approach of iterating through every item, which caused O(n²) performance.
**After:**
> This function uses a hash map for O(1) lookups, avoiding the O(n²) cost of naive iteration.

### 31. Forced punchlines and dramatic fragments
**Problem:** One short sentence adds emphasis; repeated dramatic fragments make each sentence a forced punchline.
**Before:**
> AlphaEvolve arrived. No preference for symmetry. No aesthetic prior. No human taste. The old rules were gone.
**After:**
> AlphaEvolve's indifference to symmetry and human-looking designs weakened older search assumptions.

### 32. Formulaic sayings

**Watch:** X is the Y of Z, X becomes a trap, X is a mirror, and metaphors of language, currency, or architecture.
**Problem:** Vague sayings make ordinary claims sound profound. Replace them with specific claims.
**Before:**
> Symmetry is the language of trust. Efficiency becomes a trap when teams forget the human layer.
**After:**
> Symmetric layouts often feel predictable. Teams can over-optimize workflows and overlook actual use.

### 33. Fake-candid openings

**Watch:** Honestly?, Look, Here's the thing, Let's be honest, and Real talk as standalone hooks or staged pauses.
**Problem:** Staged pauses and claims of honesty precede routine points. State the point directly.
**Before:**
> Is it worth the price? Honestly? It depends on how often you'll use it.
**After:**
> Whether it's worth the price depends on how often you'll use it.

### 34. Answering objections no one raised

**Watch:** I'm not saying, Don't get me wrong, This isn't about, and Some might say... but without a real objection.
**Problem:** Prose defends against unnamed objections. Direct limits, such as the API is not thread-safe, are valid.
**Before:**
> I'm not saying documentation doesn't matter; the issue is whether the agent can use the instruction when it acts.
**After:**
> The issue is whether the agent can use the instruction when it acts.

Keep substantive claims and objections with named sources or full answers; remove only unsupported defenses.

### 35. Rejecting fake alternatives

**Watch:** A tempting option would be, One might be tempted to, You might think... but, and Some would suggest.
**Problem:** A dismissed, unused option may be drafting residue. Remove it and state the actual constraint.
**Before:**
> Tokens rotate daily in place; clients refresh. A tempting cron restart would drop sessions, so we reject it.
**After:**
> Tokens rotate daily in place; clients refresh.

One rejection may help; several unrelated ones suggest residue. Keep new information and rewrite around the main point.

## Check for false positives

### What not to flag

A person may use some of these patterns. Do not treat any item below as proof by itself:

- **Polished style.** Professionals and editors produce consistent grammar and style; polish does not prove AI use.
- **Mixed casual and formal styles.** This can reflect the writer's field, age, or personal habits.
- **Dry prose.** Bland or robotic writing alone lacks the specific patterns needed to infer AI use.
- **Formal or academic words.** §7 lists specific words that AI writing overuses. Do not simplify every formal word.
- **Letter-style opening or closing on a comment.** Salutations and sign-offs predate ChatGPT by centuries.
- **Lone transitions.** Additionally, moreover, or consequently matter as clusters; one however is not a tell.
- **Curly quotes alone.** macOS, Word, Google Docs, and most CMSes curl quotes; look for other patterns too.
- **Em dashes alone.** Editors and journalists use them; look for formulaic sales rhythm too.
- **One short sentence for emphasis.** Flag dramatic fragments only when several appear in a row.
- **Deliberate repeated openings.** Keep repetition that builds rhythm or pressure, such as She came. She saw.
- **Honestly or look mid-sentence.** These are normal casual words; flag only theatrical standalone openings.
- **Useful limits.** Keep scope, legal and safety notices, corrections, named objections, replies, and FAQ answers.
- **Real alternatives.** Keep plausible options in designs, tutorials, or arguments; cut implausible, dismissed asides.
- **Unsourced claims.** Most of the web is unsourced. Lack of citations doesn't prove anything.
- **Correct, complex formatting.** Visual editors and templates produce clean output without any AI.
- **Secondhand text.** Preserve watched phrases quoted, titled, named, or discussed in examples.

When uncertain, seek several patterns together. One em dash proves nothing; clustered stock patterns say more.

### Human details to keep

These details often carry the writer's voice. Keep them unless they hurt the meaning:

- **Specific details.** Keep real addresses, odd quotes, and phrases like the lawyer upstairs from my dentist.
- **Mixed feelings.** Keep unresolved tension, such as I mostly like this, but something about it bothers me.
- **Dated references.** Keep era-specific slang, memes, and in-jokes; models may lag by a year or more.
- **Deliberate first-person choices.** Keep a cut or word choice when the writer can explain why it belongs.
- **Sentence length variety.** Preserve changes in length; AI prose tends toward an even, medium-length rhythm.
- **Asides and self-corrections.** Preserve spontaneous interruptions, such as (I almost said almost, but I was sure.)
- **Pre-ChatGPT edits.** Text from before its November 30, 2022 launch is rarely AI-written.

---

## How to return the result

**Pasted text (default).** Return the draft, a short list of remaining AI patterns, and the final rewrite.

**File mode.** Run all steps; save only final prose edits, preserving non-prose and URLs. Report a short summary.

**Embedded mode.** When another task invokes this skill, return only the final text.

## Rewrite process

1. Read the source and mark each AI pattern.
2. Draft and read aloud. Check rhythm, details, simple verbs such as is and has, and appropriate formality.
3. Ask two questions:
   - **"What still sounds AI-generated?"**
   - **"Did the rewrite add or remove any fact, name, number, date, quote, citation, ranking, or other claim?"**
   Treat any unsupported addition or lost claim as an error.
4. Rewrite naturally; recast awkward paragraphs around their main point instead of patching phrases. Apply §14.

Return the result required by [How to return the result](#how-to-return-the-result).

## Source

WikiProject AI Cleanup maintains [the source guide][source] from reviews of AI-generated Wikipedia text.

Wikipedia attributes generic output to statistical next-word prediction favoring broadly applicable continuations.

[source]: https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing
