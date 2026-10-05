# leadpipe no servidor — você, o Mac e mais uma pessoa, ao mesmo tempo

O que você vai ter no fim: um endereço tipo `app.seudominio.com` que abre o
painel de qualquer lugar, com login por email, para duas pessoas. O PC pode
ficar desligado. Custo: **~$6/mês**.

## Por que assim

| Peça | Para quê |
|---|---|
| VPS **nos EUA** | O servidor roda 24/7 e, de quebra, dá um **IP americano** ao scraping — que é a causa raiz dos leads do Brasil que o código hoje filtra com quatro camadas de gambiarra. |
| Docker | O Chromium do Playwright precisa de umas 40 bibliotecas de sistema. Na imagem elas já vêm; fora dela, é uma tarde caçando `.so` faltando. |
| Cloudflare Tunnel | O servidor **não abre porta nenhuma** na internet. O túnel sai de dentro. Não há o que varrer nem senha para forçar. |
| Cloudflare Access | O login de verdade: cada pessoa entra com o email dela, por código. Grátis até 50 usuários. Tirar o acesso de alguém é apagar o email da lista. |

**A contrapartida honesta:** IP de datacenter toma mais captcha do Google Maps
que IP residencial, e no servidor não tem ninguém para resolver. O código
detecta, espera e segue, então degrada em vez de quebrar. Se o sourcing ficar
ruim, a saída é rodar `lp source` no PC de casa e importar o CSV no servidor.
Sourcing é semanal; o painel é diário — vale a troca.

---

## 1. Criar o servidor (5 min)

[Hetzner](https://www.hetzner.com/cloud) CPX21 em **Ashburn ou Hillsboro** (~$8/mês,
3 vCPU, 4 GB) ou [DigitalOcean](https://www.digitalocean.com) em **NYC/SFO**
(~$12/mês, 2 GB). Ubuntu 24.04. Suba sua chave SSH na criação.

Não desça de 2 GB de RAM: o Chromium abre 4 a 6 abas em paralelo na
qualificação e é ele quem decide o tamanho da máquina.

## 2. Preparar o servidor (1 comando)

```bash
ssh root@SEU_IP
bash <(curl -fsSL https://raw.githubusercontent.com/pato15z/claude-1/claude/tender-fermi-1albbv/deploy/setup-vps.sh)
```

Instala Docker, baixa o código em `/opt/leadpipe`, fecha o firewall (só SSH
entra), cria o `.env` com uma senha forte já gerada e agenda o backup diário.

## 3. Criar o túnel na Cloudflare (10 min)

Precisa do seu domínio já apontado para a Cloudflare (nameservers dela).

1. [dash.cloudflare.com](https://dash.cloudflare.com) → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel** → **Cloudflared**
2. Dê um nome (`leadpipe`) e salve. A tela mostra um comando de instalação com um **token** longo — copie só o token.
3. Aba **Public Hostname** → **Add a public hostname**:
   - Subdomain: `app` · Domain: `seudominio.com`
   - Type: `HTTP` · URL: `app:8090`

   O `app` aqui é o nome do container, não um endereço de internet. O túnel
   fala com ele pela rede interna do Docker.
4. No servidor, cole o token:
   ```bash
   nano /opt/leadpipe/deploy/.env     # campo CLOUDFLARE_TUNNEL_TOKEN
   ```

Os nomes de menu da Cloudflare mudam de tempos em tempos. Se não achar um,
procure por "Tunnels" na busca do painel.

## 4. Colocar o login por email (5 min)

Sem isto, qualquer um com o endereço cai no painel (restaria só a senha do app).

1. **Zero Trust** → **Access** → **Applications** → **Add an application** → **Self-hosted**
2. Domínio: `app` + `seudominio.com`
3. Em **Policies**, crie uma: Action **Allow**, Include → **Emails** → seu email **e o do seu assistente**
4. Salve. O método de login padrão é código por email, não precisa configurar nada.

Para tirar o acesso de alguém depois: apaga o email dessa política. Leva 10 segundos.

## 5. Mandar os seus dados (15 min, a parte que ninguém pode pular)

Os 1.015 leads e os 982 sites existem **só no HD do PC Windows** — nada disso
está no git.

No Windows, **feche o app primeiro** (`Ctrl+C` na janela do `app.bat`), para o
banco fechar o arquivo de escrita pendente. Depois, no PowerShell, dentro da
pasta do leadpipe:

```powershell
scp -r data root@SEU_IP:/opt/leadpipe/
```

Se a pasta for grande (as imagens e vídeos pesam), compacte antes:

```powershell
tar -czf data.tgz data
scp data.tgz root@SEU_IP:/opt/leadpipe/
```
```bash
# no servidor
cd /opt/leadpipe && tar -xzf data.tgz && rm data.tgz
```

## 6. Subir

```bash
cd /opt/leadpipe/deploy
docker compose up -d --build        # o primeiro build leva ~5 min (Chromium)
docker compose logs -f app
```

Confira que os dados chegaram:

```bash
docker compose exec app leadpipe db sql "SELECT COUNT(*) FROM leads"
```

Tem que dizer **1015**. Se der 0, o banco não veio — refaça o passo 5.

Abra `https://app.seudominio.com`. Deve pedir seu email, mandar um código, e
então abrir o painel.

---

## O dia a dia

```bash
cd /opt/leadpipe/deploy

docker compose logs -f app                     # ver o que está acontecendo
docker compose restart app                     # reiniciar
docker compose exec app leadpipe doctor        # checar a máquina
docker compose exec app leadpipe db backup     # backup na hora
./backup.sh                                    # backup + limpeza dos antigos

# atualizar o código depois que eu mexer em algo
git -C /opt/leadpipe pull && docker compose up -d --build
```

## Backup — leia uma vez

O banco agora mora no servidor. Se a máquina morrer, vão junto os 1.015 leads
e todo o estado das vendas. Duas camadas:

1. **Automática:** `backup.sh` roda às 4h e guarda 14 dias em `data/backups/`.
   Já está agendada.
2. **Fora do servidor:** ligue o *snapshot* automático no painel do provedor
   (~$1,20/mês na DigitalOcean). Backup que mora no mesmo disco que o banco
   não é backup — é cópia.

De vez em quando, traga um para o seu PC:

```bash
scp root@SEU_IP:/opt/leadpipe/data/backups/$(ssh root@SEU_IP 'ls -1t /opt/leadpipe/data/backups | head -1') .
```

## Duas pessoas mexendo ao mesmo tempo

O banco é SQLite em modo WAL, com um único processo servindo. Duas pessoas
clicando juntas funciona sem conflito. O que **não** funciona é rodar o app no
servidor e no PC ao mesmo tempo: são dois bancos, duas realidades, e você perde
trabalho. Depois que isto subir, o PC vira só máquina de gravar vídeo.

## Quando o sourcing tomar captcha

```bash
# no PC de casa, com IP residencial
lp source maps --vertical "roof cleaning" --state OH --headful
lp db export --status NOVO            # gera data/leads.csv
# sobe o CSV e importa no servidor
scp data/leads.csv root@SEU_IP:/opt/leadpipe/data/
docker compose exec app leadpipe source import-csv /data/leads.csv --vertical "roof cleaning"
```

Dedup por place id, telefone e endereço é feito na importação, então repetir
lead não cria duplicata.
