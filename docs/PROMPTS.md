# Veridge — Human Prompt Cookbook

Copy-paste prompts for collaborators. Each one is self-contained and tells the agent (Claude Code
or Codex) what to do; for the full protocol see [`AGENT_PLAYBOOK.md`](AGENT_PLAYBOOK.md).

Rule of thumb: **new project → just set it up. Existing project → evaluate first, install only
after I approve.** Veridge is a per-machine dev tool — never a project dependency — and `.veridge/`
is always gitignored.

---

## 1. Prepare a NEW project — with Codex

```
Configura Veridge per questo repository nuovo. Sei Codex, ma il team usa anche Claude.
1. Verifica `veridge --version`; se manca: pip install "veridge[treesitter,mcp]".
2. `veridge build .` dalla radice; controlla che `veridge stats` sia sensato e senza errori.
3. Esegui SIA `veridge integrate codex` SIA `veridge integrate claude` (servono entrambi).
4. Assicurati che `.gitignore` contenga `.veridge/` (aggiungilo se manca).
5. `veridge install-hook` (ricostruzione automatica post-commit).
6. Committa SOLO i file di config (.mcp.json, .codex/config.toml, CLAUDE.md, AGENTS.md, .gitignore).
   NON committare `.veridge/`. NON aggiungere veridge alle dipendenze del progetto.
Riepiloga cosa hai fatto e cosa devo approvare (es. fidarsi del server MCP).
```

## 2. Prepare a NEW project — with Claude

```
Configura Veridge per questo repository nuovo. Sei Claude Code, ma il team usa anche Codex.
1. Verifica `veridge --version`; se manca: pip install "veridge[treesitter,mcp]".
2. `veridge build .` dalla radice; verifica che `veridge stats` sia proporzionato e senza errori.
3. Esegui SIA `veridge integrate claude` SIA `veridge integrate codex` (servono entrambi).
4. Assicurati che `.gitignore` contenga `.veridge/` (aggiungilo se manca).
5. `veridge install-hook` (ricostruzione automatica post-commit).
6. Committa SOLO i file di config (.mcp.json, .codex/config.toml, CLAUDE.md, AGENTS.md, .gitignore).
   NON committare `.veridge/`. NON aggiungere veridge alle dipendenze del progetto.
Riepiloga cosa hai fatto e cosa devo approvare (es. fidarmi del server MCP di progetto).
```

## 3. EXISTING project — Claude — evaluate first, install after

```
Sei in un progetto esistente già avviato. NON installare né configurare nulla finché non te lo dico.

FASE 1 — VALUTA (sola lettura, niente da committare):
1. `veridge --version` (installa con pip install "veridge[treesitter,mcp]" solo sulla mia macchina se manca).
2. `veridge build .` (scrive SOLO .veridge/, che cancelleremo se rinunciamo).
3. Analizza e DISTINGUI i falsi positivi di veridge dagli errori reali del progetto:
   - `veridge stats`  -> conteggi simboli/import/call proporzionati al codice?
   - `veridge gate`   -> ref rotti & drift: quali sono link morti VERI vs rumore mal-parsato?
   - `veridge map` e `veridge tour` -> la struttura rispecchia la realtà?
   - `veridge impact <un file centrale>` -> il raggio d'impatto è corretto, anche cross-package?
   - `veridge focus "<un task reale del progetto>"` -> la fetta restituita è quella che servirebbe?
4. Compila il REPORT (sotto) e FERMATI: mostramelo. NON committare, NON aprire issue, NON inviare nulla.

FASE 2 — solo se APPROVO io:
   - installa (passi del prompt "nuovo progetto" via Claude);
   - prepara, PER MIA CONFERMA: (a) le segnalazioni al team sui problemi del PROGETTO;
     (b) l'eventuale issue a veridge (github.com/galimar/veridge/issues) con stats + bug + fix proposti.
   Non inviare/aprire nulla all'esterno senza il mio ok esplicito.

REPORT:
## Veridge eval — <repo> @ <commit> — veridge <ver>
Profilo:   <linguaggi, ~N file, monorepo?, framework>
Copertura: files=  symbols=  imports=  calls=  references=
Risolto bene:             …
Falsi positivi (veridge): …                          -> veridge
Gap (veridge non ha visto): …                        -> veridge
Problemi del progetto:    …                          -> team
Fix proposti a veridge:   …                          -> veridge
Verdetto: installare / non installare — perché …
```

## 4. EXISTING project — Codex — evaluate first, install after

```
Sei in un progetto esistente già avviato, e sei Codex. NON installare né configurare nulla finché non te lo dico.

FASE 1 — VALUTA (sola lettura):
1. `veridge --version` (se manca: pip install "veridge[treesitter,mcp]" solo sulla mia macchina).
2. `veridge build .` (scrive SOLO .veridge/, lo cancelliamo se rinunciamo).
3. Analizza e distingui falsi positivi di veridge vs errori reali del progetto:
   `veridge stats`, `veridge gate`, `veridge map`, `veridge tour`,
   `veridge impact <file centrale>`, `veridge focus "<task reale>"`.
4. Compila il REPORT (stesso template del flusso Claude) e FERMATI: mostramelo.
   NON committare, NON aprire issue, NON inviare nulla.

FASE 2 — solo se APPROVO io:
   - installa (esegui SIA `veridge integrate codex` SIA `veridge integrate claude`, + .gitignore .veridge/ + install-hook + commit dei soli file di config);
   - prepara per mia conferma: (a) segnalazioni al team sui problemi del progetto;
     (b) eventuale issue a veridge con stats + bug + fix. Niente invii esterni senza il mio ok.
```

## 5. Multiple agents on one project (Claude + Codex)

```
Stiamo lavorando con più agenti (Claude e Codex) su questo repo con Veridge. Regole:
- Prima di editare: `focus "<task>"` per la fetta minima rilevante.
- Prima di chiudere: `impact --diff` per il raggio d'impatto della tua modifica.
- Dopo modifiche (tue o dell'altro agente): ricostruisci (`veridge build .`) o affidati al post-commit hook.
  Se `health`/`gate` dice "stale", RICOSTRUISCI prima di fidarti di impact/focus.
- `.veridge/` è locale e gitignored: non committarlo mai; ogni agente costruisce il suo (è deterministico -> stessa mappa).
- Coordina tramite il GRAFO e i COMMIT, non assumere lo stato dell'altro agente. Preferisci i tool veridge al re-grep.
```
