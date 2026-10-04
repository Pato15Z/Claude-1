# Para colar no Claude Code do Mac novo

Pré-requisitos antes de colar:

1. Creative Cloud instalado, com After Effects e Premiere Pro já baixados.
2. **Abra e feche cada um deles uma vez.** Isso cria a árvore de preferências;
   restaurar antes disso faz o app sobrescrever o que você acabou de copiar.
3. A pasta `BackupAdobe` (vinda do PC antigo) já baixada, por exemplo em `~/Downloads`.

---

```
Acabei de migrar de um PC Windows para este Mac. Tenho um backup das minhas
configurações do After Effects e do Premiere Pro em ~/Downloads/BackupAdobe
(ajuste o caminho se for outro).

O kit de restauração está em https://github.com/pato15z/claude-1, branch
claude/hopeful-shannon-8tpgf4, pasta migracao-mac/.

Faça o seguinte, nesta ordem:

1. Clone o repositório e leia migracao-mac/README.md e migracao-mac/MAPA-CAMINHOS.md.
2. Confirme que o After Effects e o Premiere já foram abertos uma vez: verifique se
   existem ~/Library/Preferences/Adobe/After Effects/<versão>/ e
   ~/Library/Preferences/Adobe/Premiere Pro/<versão>/. Se não existirem, pare e me avise.
3. Rode o restaurador em modo seco primeiro e me mostre o que ele faria:
      bash migracao-mac/scripts/02-restaurar-mac.sh --origem ~/Downloads/BackupAdobe
4. Se o plano fizer sentido, aplique só a classe A (scripts, presets, mogrt, epr,
   LUTs, fontes, extensões CEP):
      bash migracao-mac/scripts/02-restaurar-mac.sh --origem ~/Downloads/BackupAdobe --apply
   Partes que gravam em /Applications e /Library pedem sudo — me avise antes.
5. Abra o After Effects e confirme: meus scripts aparecem no menu File > Scripts,
   e meus presets em Effects & Presets. Abra o Premiere e confirme os presets de
   efeito. Me diga o que apareceu e o que não apareceu.
6. SÓ DEPOIS disso, se eu confirmar que quero tentar recuperar os workspaces,
   rode com --prefs. Esse passo é o arriscado: as prefs carregam configuração de
   GPU, RAM e cache de disco do PC antigo. O script faz backup automático do
   estado atual antes de sobrescrever — me diga onde ele salvou.
7. Leia migracao-mac/PLUGINS.md mais o PLUGINS-ENCONTRADOS.csv do backup e monte
   a lista final de plugins que preciso reinstalar, marcando para cada um se tem
   build nativo Apple Silicon. Não instale nada — só a lista.

Regras:
- Nunca rode o script inteiro com sudo. Arquivo da minha home pertencendo ao root
  quebra o Adobe de um jeito difícil de diagnosticar.
- Se algo falhar, me mostre o erro real em vez de tentar um contorno silencioso.
```

---

## Depois: ajustes que nenhum script faz

**Cache de disco e RAM.** AE → Settings → Media & Disk Cache. Os valores herdados
apontam para discos do PC antigo. Aponte o cache para o SSD interno e deixe
pelo menos 20% do espaço livre.

**Atalhos de teclado.** Refaça à mão. O arquivo do AE é nomeado por plataforma e os
modificadores `Ctrl` não viram `Cmd` sozinhos — forçar a migração gera conflitos
com atalhos do sistema que são piores que reconfigurar do zero.

**Fontes.** Abra um projeto antigo e procure por aviso de fonte faltando ou
substituída. Fonte com mesmo nome e foundry diferente troca silenciosamente e o
layout de texto muda sem avisar.

**Projetos com mídia linkada.** Os caminhos dentro do `.aep`/`.prproj` são do
Windows (`C:\...`). O Premiere e o AE vão pedir relink na primeira abertura.
Manter a estrutura de pastas relativa igual à do PC antigo reduz isso a um
relink por projeto em vez de um por arquivo.
