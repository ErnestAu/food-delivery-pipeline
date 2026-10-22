# Vendored skills

The five `hig-*` skills here are copied from
[raintree-technology/apple-hig-skills](https://github.com/raintree-technology/apple-hig-skills)
at commit `fdc35993d580730a60b827ed39adc6c9991ade41` (2026-10-12) and used for the
dashboard redesign.

- `*/SKILL.md` and `LICENSE` are MIT-licensed, © Raintree Technology. Committed as-is.
- `*/references/` holds excerpts of Apple's Human Interface Guidelines, © Apple Inc.
  The MIT license doesn't cover them, so they stay local and are gitignored. Each
  skill's index links its references; fetch them with:

  ```bash
  SHA=fdc35993d580730a60b827ed39adc6c9991ade41
  for s in hig-foundations hig-components-layout hig-components-content hig-components-status hig-patterns; do
    mkdir -p .claude/skills/$s/references
    for f in $(gh api "repos/raintree-technology/apple-hig-skills/contents/skills/$s/references?ref=$SHA" --jq '.[].name'); do
      gh api "repos/raintree-technology/apple-hig-skills/contents/skills/$s/references/$f?ref=$SHA" --jq .content | base64 -d > .claude/skills/$s/references/$f
    done
  done
  ```

To update, re-copy the `SKILL.md` files from a newer commit and change the hash above.
