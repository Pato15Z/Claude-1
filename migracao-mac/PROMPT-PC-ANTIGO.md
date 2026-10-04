# Para colar no Claude Code do PC antigo (Windows)

Se o PC antigo ainda liga e tem Claude Code instalado, cole o texto abaixo.
Se não tiver, pule e rode o script à mão — as instruções estão no final.

---

```
Preciso empacotar minhas configurações do After Effects e do Premiere Pro para
migrar para um Mac novo. O kit de migração está no repositório
https://github.com/pato15z/claude-1, branch claude/hopeful-shannon-8tpgf4,
pasta migracao-mac/.

Faça o seguinte:

1. Clone o repositório (ou baixe só a pasta migracao-mac/).
2. Leia migracao-mac/README.md e migracao-mac/MAPA-CAMINHOS.md para entender a
   divisão entre classe A (portável), classe B (binário, não migra) e classe C
   (preferências, migra com risco).
3. Rode migracao-mac/scripts/01-inventario-windows.ps1 em PowerShell como
   Administrador. Ele cria uma pasta BackupAdobe na Área de Trabalho.
4. Abra os CSVs gerados e me mostre, em texto:
   - quantos plugins foram encontrados e quais são (PLUGINS-ENCONTRADOS.csv),
     agrupados por pasta/fabricante, não arquivo a arquivo;
   - quais extensões CEP existem (EXTENSOES-CEP.csv);
   - o tamanho total do backup por categoria (INVENTARIO.csv);
   - quantos projetos .aep/.prproj existem e onde estão os maiores (PROJETOS.csv).
5. Se alguma categoria tiver vindo vazia, investigue o motivo antes de concluir:
   pode ser versão do Adobe em pasta diferente da esperada, ou falta de permissão.
   Não relate sucesso em categoria que veio zerada.
6. Compacte a pasta BackupAdobe em um .zip e me diga o tamanho final.

Não copie plugins binários (.aex/.dll) — o script já os ignora de propósito,
porque binário Windows não roda em macOS.
```

---

## Sem Claude Code no PC antigo

1. Baixe a pasta `migracao-mac` do repositório.
2. Botão direito no Menu Iniciar → **Terminal (Admin)** ou **PowerShell (Admin)**.
3. Rode:

```powershell
cd <pasta onde você salvou>\migracao-mac\scripts
Set-ExecutionPolicy -Scope Process Bypass -Force
.\01-inventario-windows.ps1
```

4. Espere. A varredura de projetos percorre todos os discos e é a parte lenta;
   se demorar demais, interrompa com Ctrl+C — os arquivos de configuração já
   terão sido copiados antes dessa etapa.
5. Compacte a pasta `BackupAdobe` da Área de Trabalho e mande para o Drive ou
   para um HD externo.

### Se o PC antigo não liga mais

Tire o SSD/HD, ponha num case USB, conecte no Mac e me avise: os caminhos
`Users/<seu-usuário>/AppData/Roaming/Adobe/...` continuam legíveis a partir do
macOS, e dá para extrair tudo direto do disco montado em `/Volumes/`.
