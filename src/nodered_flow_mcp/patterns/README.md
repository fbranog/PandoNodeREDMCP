# Pattern library

One directory per pattern:

```
<name>/
  metadata.yaml            # name, purpose, applicable_node_types, tags, provenance
  flow.json                # exemplar flow (secrets removed)
  design_constraints.md
  validation_rules.yaml
  known_limitations.md
```

Patterns are curated by hand from the example flows in `reference/projects`.
Each one should state provenance: verified | observed | proposed.
