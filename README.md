# Claude-1

Repositório pessoal de configuração do Claude Code.

## Skills instaladas

| Skill | O que faz | Como usar |
|---|---|---|
| [`llm-council`](.claude/skills/llm-council/) | Roda uma pergunta/decisão por um conselho de 5 advisors que analisam de forma independente, revisam uns aos outros anonimamente e entregam um veredito final. | Diga "council this", "run the council on ...", "pressure-test this", "stress-test this" ou "war room this". |

As skills ficam em `.claude/skills/<nome>/SKILL.md` e são carregadas automaticamente
pelo Claude Code em qualquer sessão aberta dentro deste repositório.

## Kit de migração Windows → Mac (Adobe)

[`migracao-mac/`](migracao-mac/) — scripts e documentação para levar layouts, scripts,
presets e configurações do After Effects e do Premiere Pro de um PC Windows para um Mac,
mais o inventário de plugins para reinstalação manual.

| Arquivo | Para quê |
|---|---|
| [`README.md`](migracao-mac/README.md) | visão geral, classes de portabilidade, ordem de execução |
| [`PROMPT-PC-ANTIGO.md`](migracao-mac/PROMPT-PC-ANTIGO.md) | texto para colar no Claude Code do PC antigo |
| [`PROMPT-MAC.md`](migracao-mac/PROMPT-MAC.md) | texto para colar no Claude Code do Mac |
| [`MAPA-CAMINHOS.md`](migracao-mac/MAPA-CAMINHOS.md) | tabela de caminhos Windows ↔ macOS |
| [`PLUGINS.md`](migracao-mac/PLUGINS.md) | inventário de plugins e triagem Apple Silicon |
| [`ACHADOS-DRIVE.md`](migracao-mac/ACHADOS-DRIVE.md) | o que já existe no Google Drive |
| [`scripts/`](migracao-mac/scripts/) | `01-inventario-windows.ps1`, `01-inventario-mac.sh`, `02-restaurar-mac.sh` |

Comece por `PROMPT-PC-ANTIGO.md`: o inventário tem que rodar na máquina que tem os arquivos.

### Créditos

`llm-council` foi criada por [Ole Lehmann](https://x.com/itsolelehmann), a partir da
metodologia [LLM Council](https://github.com/karpathy/llm-council) do Andrej Karpathy.
Fonte: https://github.com/aiwithremy/claude-skills-llm-council
