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

## Scope notes

Veridge is **read-only on your sources** and has **no runtime dependencies in its core**, which
keeps its attack surface small. The most relevant areas:

- the generated `view.html` inlines graph data — node ids/labels are escaped (every `<` becomes
  `<`) so a crafted file name cannot inject script;
- the optional `[treesitter]` and `[mcp]` extras pull third-party packages — report issues in
  those upstreams as well when relevant.
