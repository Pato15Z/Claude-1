# Claude-1

Repositório pessoal de configuração do Claude Code.

## Contexto do usuário

[`CLAUDE.md`](CLAUDE.md) guarda meu contexto pessoal (quem sou, situação de
trabalho, capacidade real de horas, stack e projetos ativos). O Claude Code
carrega esse arquivo automaticamente em qualquer sessão aberta neste
repositório, então não preciso reexplicar o básico a cada conversa.

## Skills instaladas

| Skill | O que faz | Como usar |
|---|---|---|
| [`llm-council`](.claude/skills/llm-council/) | Roda uma pergunta/decisão por um conselho de 5 advisors que analisam de forma independente, revisam uns aos outros anonimamente e entregam um veredito final. | Diga "council this", "run the council on ...", "pressure-test this", "stress-test this" ou "war room this". |

As skills ficam em `.claude/skills/<nome>/SKILL.md` e são carregadas automaticamente
pelo Claude Code em qualquer sessão aberta dentro deste repositório.

### Créditos

`llm-council` foi criada por [Ole Lehmann](https://x.com/itsolelehmann), a partir da
metodologia [LLM Council](https://github.com/karpathy/llm-council) do Andrej Karpathy.
Fonte: https://github.com/aiwithremy/claude-skills-llm-council
