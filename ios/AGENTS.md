# iOS AGENTS.md

These rules apply only inside `ios/`.

- The current iOS subtree is a temporary legacy exception to the repo-wide non-iOS LLM-oriented refactor.
- Do not start broad iOS architecture cleanup during unrelated work.
- When touching iOS files for bug fixes or small features, avoid increasing file size or coupling, and prefer local simplification where it is low risk.
- Do not use this local exception to justify non-compliant structure anywhere outside `ios/`.
