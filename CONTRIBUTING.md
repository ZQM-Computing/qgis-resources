# Contributing

Thanks for helping make these resources more useful.

## What makes a good resource

1. The everyday problem it solves, in plain language.
2. The QGIS version it was written for (LTR version preferred).
3. The layer names, field names, and CRS assumptions it makes — stated up front.
4. Comments at the decision points: why this function, this algorithm, this tolerance.
5. Honest sharp edges: what breaks, what's slow, what to check first.

## Ground rules

- Do not submit real parcel, utility, customer, infrastructure-sensitive, or personally identifying data in examples or screenshots.
- Keep coordinates and CRS explicit in every example that measures anything.
- Python snippets must at minimum parse cleanly (`python -m py_compile`) and follow the existing header-docstring format: what it does, where to run it, tested version, what to adjust.
- Styles (.qml) must be well-formed XML exported from, or faithful to, QGIS 3.x.
- Expressions should be copy-pasteable into the expression editor with placeholder names clearly marked.

## Style

- Markdown files use sentence-case headings.
- Code blocks are fenced with a language tag (`sql`, `python`, or none for raw expressions).
- Prefer small, single-purpose resources over framework-sized ones.
