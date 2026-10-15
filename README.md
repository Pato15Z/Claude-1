# Claude-1

Repositório pessoal de configuração do Claude Code.

## Skills instaladas

| Skill | O que faz | Como usar |
|---|---|---|
| [`llm-council`](.claude/skills/llm-council/) | Roda uma pergunta/decisão por um conselho de 5 advisors que analisam de forma independente, revisam uns aos outros anonimamente e entregam um veredito final. | Diga "council this", "run the council on ...", "pressure-test this", "stress-test this" ou "war room this". |
| [`reverse-engineer-anything`](.claude/skills/reverse-engineer-anything/) + MCP `rea` ([`.mcp.json`](.mcp.json)) | REA ([morluto/rea](https://github.com/morluto/rea), `rea-agents@6.5.0`): engenharia reversa de binários nativos, .NET, Electron/JS (ASAR), APK, firmware, WASM, capturas de rede e browser, com Evidence rastreável. 207 tools MCP. | Peça "faça engenharia reversa de X" / "como funciona a feature Y neste app/binário". Análise nativa exige Ghidra/Hopper/IDA instalados; JS/Electron, Go/Rust metadata, PE resources etc. funcionam sem engine. |

As skills ficam em `.claude/skills/<nome>/SKILL.md` e são carregadas automaticamente
pelo Claude Code em qualquer sessão aberta dentro deste repositório.

### Créditos

`llm-council` foi criada por [Ole Lehmann](https://x.com/itsolelehmann), a partir da
metodologia [LLM Council](https://github.com/karpathy/llm-council) do Andrej Karpathy.
Fonte: https://github.com/aiwithremy/claude-skills-llm-council
