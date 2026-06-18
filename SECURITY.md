# Security Policy

## Supported versions

Veridge is in alpha; security fixes target the **latest released version** on PyPI.

## Reporting a vulnerability

Please report security issues **privately**, not as a public issue:

- Open a private advisory via **GitHub → Security → Report a vulnerability**
  (<https://github.com/galimar/veridge/security/advisories/new>), or
- contact the maintainer through the repository's profile.

Include a description, affected version, and a minimal reproduction if possible. You'll get an
acknowledgement, and a fix or mitigation plan once the report is triaged.

## Dependency auditing

Every CI run (and a weekly scheduled run) audits Veridge's full dependency closure with
[`pip-audit`](https://github.com/pypa/pip-audit) against the PyPA Advisory Database, and **fails
on any known advisory**. Because the core has zero runtime dependencies, that closure is just the
`[treesitter]` extra (`tree-sitter` + `tree-sitter-language-pack`). The audit is part of the
public [CI workflow](.github/workflows/ci.yml) — an open, reproducible report, not a third-party
scanner's paywalled claim. To reproduce locally:

```bash
pip install -e ".[treesitter]"
pip freeze --exclude-editable > audit-deps.txt
pipx run pip-audit -r audit-deps.txt --strict --desc
```

## Scope notes

Veridge is **read-only on your sources** and has **no runtime dependencies in its core**, which
keeps its attack surface small. The most relevant areas:

- the generated `view.html` inlines graph data — node ids/labels are escaped (every `<` becomes
  `<`) so a crafted file name cannot inject script;
- the optional `[treesitter]` and `[mcp]` extras pull third-party packages — report issues in
  those upstreams as well when relevant.
