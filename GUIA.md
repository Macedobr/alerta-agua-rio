# Passo a passo da instalação

Guia para colocar o Alerta Água RJ no ar, sem depender do seu PC.
Tempo estimado: **10 a 15 minutos**. Custo: **R$ 0**.

O que você vai precisar:

- uma conta no **GitHub** (se não tiver, criamos no passo 0);
- o **Telegram** instalado no celular ou no PC;
- Windows 10 ou 11 com o **winget** (vem instalado; se não tiver, o passo 3
  mostra como resolver).

---

## Passo 0 — Conta no GitHub (só se ainda não tiver)

1. Abra <https://github.com/signup>
2. Informe e-mail, senha e um nome de usuário (ex.: `macedo-rj`)
3. Confirme o e-mail que o GitHub enviar

Guarde o **nome de usuário** — ele vai aparecer nos endereços no final.

---

## Passo 1 — Criar o bot no Telegram

O bot é quem vai te mandar as mensagens. Ele é criado por um bot oficial do
próprio Telegram, o **@BotFather**.

1. Abra o Telegram e busque por **@BotFather**
   (tem selo de verificação azul; é o primeiro resultado)
2. Toque em **Start** (ou envie `/start`)
3. Envie a mensagem:

   ```
   /newbot
   ```

4. Ele pergunta o **nome** do bot. Responda algo como:

   ```
   Alerta Água RJ
   ```

5. Ele pergunta o **nome de usuário**. Precisa ser único no Telegram e
   terminar com `bot`. Exemplos:

   ```
   alerta_agua_santa_cruz_bot
   alerta_agua_rj_macedo_bot
   ```

   Se já existir, ele avisa e você tenta outro.

6. Ele responde com uma mensagem assim:

   ```
   Done! Congratulations on your new bot...
   Use this token to access the HTTP API:
   123456789:AAH8xQ2kL9mN-pQrStUvWxYz0123456789
   ```

7. **Copie o token** (a linha comprida com dois-pontos). É a senha do bot:
   não compartilhe com ninguém e não cole em lugar público.

> Dica: mande `/setdescription` e `/setuserpic` para deixar o bot bonitinho.
> Não é obrigatório.

**Não feche essa conversa** — você vai voltar nela no passo 4.

---

## Passo 2 — Abrir o PowerShell na pasta do projeto

1. Abra o **Explorador de Arquivos** e entre na pasta `alerta-agua-rio`
   (a que tem `app.py`, `publicar.ps1`, `run.bat`)
2. Clique uma vez na **barra de endereço** (onde aparece o caminho)
3. Apague o que está lá, digite `powershell` e aperte **Enter**

Vai abrir uma janela azul (ou preta) já apontando para a pasta certa.

> Alternativa: segure **Shift**, clique com o botão direito numa área vazia da
> pasta e escolha **"Abrir janela do PowerShell aqui"**.

Para conferir se está no lugar certo, digite:

```powershell
dir
```

Devem aparecer `app.py`, `publicar.ps1`, `README.md` etc.

---

## Passo 3 — Rodar o script de publicação

Cole este comando e aperte **Enter**:

```powershell
powershell -ExecutionPolicy Bypass -File .\publicar.ps1
```

O que vai acontecer, etapa por etapa:

### 3.1 — Instalação de ferramentas (1/6)

Se o Git e o GitHub CLI não estiverem instalados, ele instala pelo winget.

- Pode aparecer uma janela do Windows pedindo permissão (**UAC**).
  Clique em **Sim**.
- Se aparecer contrato de licença no terminal, aceite com **Enter** ou `Y`.
- Isso pode levar 1 a 3 minutos.

> Se aparecer `winget não é reconhecido`, instale o **App Installer** pela
> Microsoft Store e rode o script de novo.

### 3.2 — Login no GitHub (2/6)

1. O script abre o navegador em <https://github.com/login/device>
2. No terminal aparece um código tipo `A1B2-C3D4`
3. Digite (ou cole) esse código no navegador
4. Clique em **Authorize github**
5. Se aparecer alguma pergunta no terminal (ex.: "Authenticate Git with your
   GitHub credentials?"), aperte **Enter** para aceitar o padrão

Volte ao terminal: deve aparecer `usuario: seu-usuario`.

### 3.3 — Criação do repositório (3/6 e 4/6)

Ele cria um repositório **público** chamado `alerta-agua-rio` na sua conta e
envia todos os arquivos. Você vai ver mensagens do Git (`Counting objects...`,
`Writing objects...`).

### 3.4 — Token do bot (5/6)

O terminal pergunta:

```
Cole o token do bot (@BotFather)
```

Cole o token do passo 1 e aperte **Enter**.
Os caracteres **não aparecem** na tela enquanto você cola — é normal.

### 3.5 — Chat id automático (5/6)

Ele valida o token e mostra:

```
bot: @seu_bot
abra o Telegram e mande um 'oi' para @seu_bot. Esperando...
```

**Agora vá ao Telegram** e mande qualquer mensagem (`oi`) para o seu bot.
Em até 10 segundos o script captura seu chat id e continua sozinho.

### 3.6 — Pages e primeira execução (6/6)

Ele liga o GitHub Pages e dispara a primeira checagem. No fim, imprime algo
como:

```
Pronto.

Repositorio: https://github.com/SEU-USUARIO/alerta-agua-rio
Acoes:       https://github.com/SEU-USUARIO/alerta-agua-rio/actions
Painel:      https://SEU-USUARIO.github.io/alerta-agua-rio/
```

---

## Passo 4 — Conferir se funcionou

### 4.1 — Telegram

Em alguns segundos deve chegar uma mensagem:

> ✅ **Monitor de abastecimento ativo**
> Vigiando as fontes a cada 2 min.
> 37 notícias relevantes no painel agora.

Se chegou, o mais importante está funcionando.

### 4.2 — GitHub Actions

1. Abra o link **Acoes** que o script mostrou
2. Deve haver uma execução com bolinha **amarela** (rodando) ou **verde** (ok)
3. Clique nela para ver o log: `Ciclo: 188 coletadas, ...`

### 4.3 — Painel

Abra o link **Painel**. Na primeira vez pode levar **1 a 2 minutos** para o
GitHub publicar. Se der 404, espere e recarregue.

---

## Se algo der errado

| Erro que aparece | O que fazer |
|---|---|
| `execution of scripts is disabled` | Use o comando completo com `-ExecutionPolicy Bypass` |
| `winget não é reconhecido` | Instale o **App Installer** na Microsoft Store |
| `git não é reconhecido` depois de instalar | Feche e reabra o PowerShell; rode o script de novo |
| `login nao concluido` | Rode `gh auth login --web` manualmente e tente de novo |
| `token invalido` | Copie o token inteiro no @BotFather (`/token`) |
| `nao consegui criar o repositorio` | Já existe um repo com esse nome; rode com `-NomeRepo outro-nome` |
| Painel dá 404 | Espere 2 min; confira **Settings → Pages** se está `main` / `/docs` |
| Nenhuma mensagem no Telegram | Confira em **Settings → Secrets** se os dois nomes estão exatos |
| Actions não roda sozinho | **Settings → Actions → General** → permita os workflows |

Para ver o script sem executar nada:

```powershell
powershell -ExecutionPolicy Bypass -File .\publicar.ps1 -Simular
```

---

## Depois de instalado

### Rodar na hora, sem esperar

No GitHub: **Actions → Monitor de abastecimento → Run workflow → Run workflow**.

### Mudar a frequência

Edite `.github/workflows/monitor.yml`, linha do `cron`:

```yaml
- cron: "*/10 * * * *"   # a cada 10 min (padrão)
- cron: "*/5 * * * *"    # tenta a cada 5 min
```

### Ajustar o que ele considera relevante

Na nuvem o app usa os valores padrão de `agua/config.py` (o `config.json` é
ignorado pelo Git para não vazar o token). Para mudar notas ou buscas, edite:

- `DEFAULTS["coleta"]["queries"]` — as buscas no Google News
- `DEFAULTS["pontuacao"]["minimo_alerta"]` — nota mínima para tocar no Telegram

Depois faça commit e push (ou edite direto no site do GitHub).

### Desligar tudo

- **Pausar alertas:** Settings → Actions → desabilitar o workflow
- **Apagar de vez:** Settings → (fim da página) → Delete this repository

O bot do Telegram continua existindo; para removê-lo, fale com o @BotFather
(`/deletebot`).

---

## O que você NÃO precisa fazer

- deixar o PC ligado;
- instalar Python;
- pagar nada;
- abrir porta no roteador.
