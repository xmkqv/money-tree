# handoff

handoff()
  log intent plainly
  log initiating request verbatim
  log later refinements that change it
  log concise handoff summary

# rules

- later refinements supersede conflicting parts of the initiating request
- an unavailable initiating request is reported as unavailable, never reconstructed
- handoff implies that any insights/assumptions/designs are likely incorrect
