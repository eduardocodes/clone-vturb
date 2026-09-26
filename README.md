# Smart VSL - Player de Alta Conversão e Hospedagem de Vídeos `v1.0.8`

[![Versão](https://img.shields.io/badge/versão-1.0.8-blue.svg)](README.md)
[![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)](docker/docker-compose-prod.yml)
[![Testes](https://img.shields.io/badge/testes-100%25%20passando-success.svg)](README.md)

Plataforma completa de alta performance para hospedagem, gerenciamento e reprodução de vídeos de vendas (VSLs) de alta conversão. O sistema conta com **Frontend** em React (Vite + TypeScript), **Backend** em Python (FastAPI + SQLAlchemy), banco de dados **PostgreSQL** orquestrado via **Docker**, suporte a armazenamento local e em nuvem via **Backblaze B2 Object Storage**, e auditoria automatizada de segurança de dependências.

---

## ⚡ Funcionalidades do Sistema

### 🎬 Gerenciamento de Vídeos
- **Criação de Vídeos em Tela Cheia**: Interface moderna de edição para cadastrar vídeos via upload de arquivo (`.mp4`, `.mov`, `.webm`, `.avi`) ou inserção de URL externa.
- **Listagem com Timestamp Completo**: Exibição da data e horário exato de envio no formato brasileiro (`DD/MM/YYYY às HH:mm`) referenciado no Horário Oficial de Brasília.
- **Paginação Inteligente**: Divisão automática da lista de vídeos em até 20 itens por página com controles intuitivos de navegação.
- **Seleção Múltipla e Exclusão em Massa**: Seleção individual ou checkbox mestre ("Selecionar Todos") para deletar múltiplos vídeos com popup centralizado de confirmação à prova de cliques acidentais.

### 🚀 Recursos Avançados por Vídeo (Configuráveis Individualmente)
- **Modo Turbo (Acelerador de Velocidade)**:
  - Velocidades predefinidas de `0.5x` até `2.0x` com controle fino via slider.
  - Switch de ativação/desativação integrado com prévia interativa ao vivo.
- **Smart Autoplay™ & Autoplay Direto com Som**:
  - **Smart Autoplay™ (Padrão)**: Inicia o vídeo automaticamente mudo para contornar o bloqueio de navegadores e exibe uma chamada animada para o visitante ativar o som, com personalização de texto, cores, tamanhos e opção de reiniciar o vídeo ao desmutar.
  - **Autoplay Direto com Som**: Inicia imediatamente com áudio ligado sem sobreposições na tela para visitantes com permissão de áudio autônomo (MEI). Caso o navegador silencie o som no primeiro segundo, exibe um badge discreto e elegante com botão para ativar o som de imediato com 1 clique.
  - **Personalização Total do Badge**: Controle de texto do aviso, texto do botão ("OUVIR", "LIGAR ÁUDIO") e seletor de cores com prévia dinâmica ao vivo.
  - **Embeds Otimizados com Iframe Permissions**: Códigos embed gerados com `allow="autoplay *; fullscreen *; encrypted-media *"` e listener de desbloqueio inteligente.
- **Player Flutuante (Picture-in-Picture / Mini-Player)**:
  - Mantém o vídeo reproduzindo no canto inferior (direito ou esquerdo) enquanto o visitante rola a página de vendas.
  - Ajuste dinâmico de largura e botão para fechar o mini-player.
- **Conteúdo Oculto (Pitch Delay da Página)**:
  - Libera seções externas da landing page (ofertas, botão de checkout, depoimentos) no momento exato do pitch de vendas.
  - Suporte a seletor CSS, auto-scroll suave até a oferta e persistência no `localStorage`.
- **Pixels de Rastreamento (Facebook, Google Ads/Tag, TikTok)**:
  - Disparo de eventos de remarketing e conversão aos 25%, 50%, 75%, 100% de reprodução e no momento do pitch.
- **Segurança & Domínios Autorizados (Whitelist & Anti-Download)**:
  - Restringe a reprodução do player exclusivamente aos domínios autorizados, bloqueando tentativas de cópia não autorizadas.
  - Proteção anti-download (desativa clique direito e downloads nativos).
- **Aparência e Estilização do Player**:
  - Personalização de cor de destaque (paleta pré-definida e seletor hexadecimal).
  - Controle de formato e estilo do botão de play com prévia dinâmica em tempo real.
  - Slider de cantos arredondados (0 a 20px) refletido instantaneamente no player.
  - Customização de controles visuais (barra de progresso, tempo do vídeo, tela cheia, volume) com tooltips explicativos.
- **Modo Vertical Celular (9:16) & Capítulos do Vídeo**:
  - Suporte nativo ao formato vertical 9:16 ideal para vídeos estilo Shorts, Reels e TikTok.
  - Marcadores de capítulos navegáveis com tempo, título descritivo e switch de ativação rápida.
- **Progresso Inteligente**:
  - Barra de progresso que anda rápido no início e desacelera no final, fazendo o vídeo parecer mais curto.
  - Intensidade Suave, Médio ou Forte, com prévia ao vivo na aba Estilização; barra apenas visual quando ativo.
- **Gráfico de Retenção VTurb com Player Centralizado**:
  - Visualização de pico e curva de retenção por segundo com thumbnail e player sincronizado.
  - Sub-abas de métricas detalhadas com taxas de engajamento e filtros temporais.

### 🔐 Autenticação e Segurança de Acesso
- **Tela de Login Moderna**: Layout em 2 colunas com formulário de login (e-mail, senha com visualização toggle e loading) à esquerda e imagem/showcase com tema de alta conversão à direita.
- **Conta Super Admin Automática**: Credenciais configuradas no `.env` (`SUPER_ADMIN_EMAIL` e `SUPER_ADMIN_PASSWORD`), sincronizadas automaticamente no banco de dados na inicialização do backend.
- **Criptografia Memory-Hard (Argon2id)**: Senhas criptografadas com `argon2-cffi` utilizando 64MB de memória RAM por cálculo (`memory_cost=65536`), 3 iterações e 4 threads, inviabilizando ataques de força bruta com GPU/ASIC.
- **Proteção de Rotas com Tokens JWT**: Todas as rotas administrativas exigem cabeçalho `Authorization: Bearer <token>`.
- **Expiração Automática de Sessão (24h) e Logout Reativo**: Tokens JWT possuem tempo de vida configurável em horas (`JWT_ACCESS_TOKEN_EXPIRE_HOURS=24h`). Ao expirar, a aplicação detecta o vencimento, encerra a sessão de forma segura e redireciona para o login com toast informativo.
- **Redefinição de Senha Segura via E-mail (Brevo)**:
  - Fluxo completo "Esqueci minha senha" com geração de token único de uso único (expiração de 1 hora).
  - Envio de e-mail transacional via API oficial do Brevo e tela dedicada de redefinição com validação de senha forte.
- **Embeds e Telemetria Públicos**: As rotas `/videos/{id}` e `/videos/{id}/events` permanecem abertas sem autenticação para permitir a incorporação de players e registro de telemetria por visitantes externos.
- **Credenciais de Desenvolvimento**:
  - **E-mail:** `admin@vturb.com`
  - **Senha:** `Admin123456!`

### 👥 Gestão de Usuários e Controle de Acesso
- **Identificação do Usuário na Barra Lateral**: Card fixo no rodapé da Sidebar exibindo o avatar dinâmico com inicial, nome completo e e-mail do usuário logado.
- **Restrição Rigorosa ao Super Admin**: O botão "Gestão de Usuário" na barra lateral e o acesso ao painel são restritos **exclusivamente** ao Super Admin oficial. Para administradores comuns e usuários normais, o botão não é exibido e qualquer tentativa de acesso via API retorna `HTTP 403 Forbidden`.
- **Edição de Usuários e Redefinição Administrativa**: Modal para edição rápida de nome e e-mail de usuários cadastrados, além de botão para disparo de redefinição de senha com modal de confirmação.
- **Abas Dedicadas com Contadores**: Separação clara entre **"Usuários Ativos"** e **"Convites Gerados"**, cada uma com contadores numéricos dinâmicos em tempo real.
- **SuperAdmin Oficial Único**: Protegido e vinculado estritamente ao e-mail definido em `SUPER_ADMIN_EMAIL` na `.env`, exibido na lista com badge exclusivo `SUPERADMIN` e proteção contra exclusão via interface e backend (`HTTP 400`). Demais cadastros são automaticamente normalizados como administradores ou usuários padrão.
- **Geração de Convites Personalizados**: Modal para criação de convites com perfil restrito a **Admin** ou **Usuário** (sem criação de convites para SuperAdmin) e tempo de expiração customizável (`1h`, `6h`, `24h`, `48h`, `7 dias`).
- **Exclusão de Convites com Confirmação**: Botão de exclusão (lixeira) para remover convites obsoletos, com popup centralizado de confirmação à prova de cliques acidentais.
- **Cópia de Link Otimizada e Toasts no Topo Direito**: Ação de cópia do link sem rolar a tela ou atualizar a página, com notificações (toasts) padronizadas no canto superior direito da tela.
- **Página de Cadastro Seguro via Convite (`/invite/:token`)**:
  - Layout totalmente responsivo e centralizado, com espaçamento equilibrado evitando cortes superiores ou inferiores em qualquer resolução.
  - Validação do convite em tempo real (bloqueia links expirados ou já utilizados).
  - Política de **Senha Forte de 12+ caracteres** com checklist visual dinâmico (mínimo 12 caracteres, maiúscula, minúscula, número, caractere especial e confirmação idêntica).
  - Criptografia com Argon2id ao persistir no banco de dados.

### 💾 Backup Automático no S3 (Backblaze B2)
- **Acesso Restrito ao Super Admin**: O botão "Backup Automático" fica posicionado **logo acima** de "Gestão de Usuário" na barra lateral e é exibido estritamente para o Super Admin oficial (`is_super_admin: true`).
- **Identidade Estética Alinhada ao VTurb**: Interface com tema claro premium (`#f8fafc` / `#ffffff`), cartões com cantos arredondados, sombras sutis e acentos em azul `#0284c7`.
- **Cards de Métricas Superiores**: Exibição em tempo real do **Último Backup** (data/hora formatada e nome do arquivo), **Próximo Backup** (horário previsto e frequência configurada), **Retenção no S3 / B2** e o novo card de **Status do Backblaze B2** (Conectado / Desconectado com aviso de pendência).
- **Três Abas Especializadas**:
  1. **Backups no S3**:
     - Card de execução imediata com botão **"Fazer Backup Agora"** que abre popup modal centralizado com indicador visual de progresso e barra de status em tempo real, gerando dump compactado com sufixo `_manual.dump.gz` para identificação visual clara na tabela (Manual vs Automático vs Importado).
     - Tabela completa de snapshots com seleção múltipla, paginação em até 20 itens, download autenticado direto do arquivo (`.dump.gz`), restauração do banco e exclusão protegida com bloqueio inteligente caso o Backblaze B2 não esteja conectado.
  2. **Agendamento Automático**:
     - Toggle de ativação/pausa da rotina periódica.
     - Frequência de execução configurável (1h, 3h, 6h, 12h, 24h, 48h, 7 dias).
     - Pasta de destino dentro do bucket S3 (`vturb/backups/`).
     - Limite de retenção máxima de backups para purga automática dos dumps mais antigos.
  3. **Importar Backup Externo**:
     - Área interativa de drag & drop para upload de arquivos `.dump`, `.dump.gz`, `.sql` e `.tar` externos diretamente para o Backblaze B2.
- **Persistência Completa de Navegação (F5)**: Ao recarregar a página (F5), a aplicação restaura exatamente a última tela e subaba acessada pelo usuário através de sincronização com `localStorage`.

---

## 📁 Estrutura de Pastas

```text
clone-vturb/
├── .gitignore                      # Arquivos e diretórios ignorados pelo Git
├── .dockerignore                   # Arquivos ignorados nas builds Docker
├── README.md                       # Documentação completa do projeto
├── BUSINESS_RULES.md               # Especificação das regras de negócio
├── DATABASE_SCHEMA_LOG.md          # Histórico de alterações e migrações do banco
├── scripts/                        # Scripts utilitários e de manutenção
│   └── audit_security.py           # Auditoria unificada de vulnerabilidades (pip-audit + npm audit)
├── docker/                         # Configuração e orquestração Docker
│   ├── docker-compose-local.yml     # Orquestração do PostgreSQL, Backend e Frontend
│   ├── backend/Dockerfile          # Imagem de produção/desenvolvimento do backend
│   └── frontend/Dockerfile         # Imagem de produção/desenvolvimento do frontend
├── backend/                        # Backend Python (FastAPI)
│   ├── .env.example                # Modelo oficial de variáveis de ambiente
│   ├── app/
│   │   ├── api/                    # Rotas e controladores REST (vídeos, health, etc.)
│   │   ├── core/                   # Configurações, banco de dados e logs
│   │   ├── models/                 # Modelos relacionais SQLAlchemy
│   │   ├── schemas/                # Schemas de validação Pydantic
│   │   ├── services/               # Camada de serviços e regras de negócio
│   │   └── main.py                 # Ponto de entrada FastAPI com Exception Handler Global
│   ├── tests/                      # Suíte de testes unitários Pytest
│   ├── pytest.ini
│   └── requirements.txt            # Dependências Python com versões fixas
└── frontend/                       # Frontend React (Vite + TypeScript)
    ├── src/
    │   ├── components/             # Componentes modulares, player e abas de vídeo
    │   ├── services/               # Cliente HTTP e integração com a API
    │   ├── types/                  # Definições de tipos TypeScript
    │   ├── tests/                  # Suíte de testes unitários Vitest
    │   ├── App.tsx
    │   └── main.tsx
    ├── package.json
    ├── vite.config.ts
    └── tsconfig.json
```

---

## 🚀 Como Executar o Projeto Localmente

### 1. Inicializando com Docker Compose (Recomendado)
Para subir o banco de dados PostgreSQL, backend e frontend de forma integrada:
```bash
docker compose -f docker/docker-compose-local.yml up -d
```

Validar o status dos containers:
```bash
docker compose -f docker/docker-compose-local.yml ps
```

### 2. Executando o Backend Individualmente
```bash
cd backend
python -m venv venv
# No Windows: venv\Scripts\activate | No Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```
Acesse a documentação interativa Swagger em: `http://localhost:8003/docs`

### 3. Executando o Frontend Individualmente
```bash
cd frontend
npm install
npm run dev
```
Acesse a aplicação no navegador em: `http://localhost:5175`

### 4. Executando em Produção com Docker Compose (Apenas Backend e Frontend)
A stack de produção foi concebida exclusivamente com os serviços do **Backend** (Uvicorn multi-worker sem reload) e **Frontend** (Build estática de alta performance servida via Nginx Alpine com Gzip e SPA Fallback):
```bash
# 1. Copie o modelo de variáveis de ambiente de produção
cp docker/.env.production.example docker/.env.production

# 2. Ajuste a URL do banco PostgreSQL de produção e suas credenciais no docker/.env.production

# 3. Suba os contêineres de produção
docker compose --env-file docker/.env.production -f docker/docker-compose-prod.yml up -d --build

# 4. Validar os serviços
docker compose --env-file docker/.env.production -f docker/docker-compose-prod.yml ps
```


---

## 🛡️ Auditoria de Segurança de Dependências

O projeto possui verificação automática de vulnerabilidades conhecidas (CVEs) para bibliotecas Python e pacotes NPM:

```bash
python scripts/audit_security.py
```
- **Backend**: Executa `pip-audit` consultando as bases oficiais OSV e PyPI.
- **Frontend**: Executa `npm audit` consultando o GitHub Advisory Database.

---

## 🧪 Testes Automatizados

### Backend (Pytest)
```bash
docker exec backend pytest -v
# ou localmente:
cd backend && pytest -v
```

### Frontend (Vitest)
```bash
cd frontend
npm test
```

---

## 📦 Imagens Docker Oficiais (Docker Hub)

| Imagem | Versão Atual | Descrição |
|---|---|---|
| `aryalvesfernandes/clone-vturb:frontend-1.0.8` | `1.0.8` | Frontend React + Vite compilado servido via Nginx Alpine com suporte a Embed e HMR |
| `aryalvesfernandes/clone-vturb:backend-1.0.8` | `1.0.8` | API FastAPI com suporte a Uvicorn Multi-Workers, Argon2id e telemetria |

### 🚀 Novidades da Versão 1.0.8
- **Refatoração Global de Clean Code & Modularização Arquitetural**:
  - Eliminação de todos os arquivos monolíticos acima de 500 linhas em 100% do projeto.
  - **Modularização de `EmbedPlayer.tsx`**: Extração de hooks especializados (`useEmbedPlayback`, `useEmbedFloatingPlayer`, `useEmbedTransparency`), submódulos visuais (`EmbedBufferingOverlay`, `EmbedFloatingCloseButton`) e utilitários puros de estilo e dimensões (`embedPlayerHelpers.ts`). Redução de 498 para 260 linhas.
  - **Modularização de `StylingVideoPreview.tsx`**: Extração de `StylingPreviewHeader`, `StylingBigPlayButton`, `StylingProgressBar`, `StylingPlayerControlsBar`, `useStylingPreviewPlayer` e `stylingPreviewHelpers.ts`. Redução de 488 para 153 linhas.
  - **Modularização de `VideoPreviewTestPage.tsx`**: Extração de `PreviewTopHeader`, `PreviewPlayerWrapper`, `PreviewMockLandingPageSections` e `useFloatingPlayerObserver`. Redução de 492 para 119 linhas.
  - **Modularização de `InvitesTable.tsx`**: Extração de `InviteTableRow`, `InvitesBulkActionsBar`, `InvitesPagination` e `inviteFormatters.ts`. Redução de 485 para 149 linhas.
  - **Modularização de `VideoEmbedTab.tsx`**: Extração de `EmbedDimensionControls`, `EmbedLivePreviewCard`, `EmbedCodeSnippetBox` e `embedDimensionHelpers.ts`. Redução de 492 para 158 linhas.
  - **Modularização de `VideoCreateView.tsx`**: Extração de `VideoSourceSection`, `ThumbnailSourceSection`, `VideoCreateHeader`, `PlayerQuickSettings`. Redução de 667 para 281 linhas.
  - **Modularização de `BackupsS3Tab.tsx`**: Extração de `BackupHistoryTable`, `RestoreBackupModal`, `ManualBackupHeader` e `backupFormatters.ts`. Redução de 603 para 122 linhas.
  - **Modularização de `VTurbRetentionChart.tsx`**: Extração de `RetentionChartCanvas`, `RetentionChartNavbar`, `RetentionChartScrubber` e `retentionChartHelpers.ts`. Redução de 534 para 189 linhas.
- **Centralização de Infraestrutura e Limpeza da Raiz**:
  - Centralização de arquivos de ambiente de produção (`.env.production`, `.env.production.example`, `docker-compose.prod.yml`) dentro da pasta estruturada `docker/`.
- **Expansão da Suíte de Testes Automatizados**:
  - Frontend ampliado para **39 suítes de teste** e **193 testes unitários** (Vitest) 100% aprovados.
  - Backend com **41 testes unitários** (Pytest) 100% aprovados.
  - Auditoria automatizada de dependências de segurança (`audit_security.py`) com **0 vulnerabilidades** no backend (pip-audit) e frontend (npm audit).
  - Ajuste de estabilidade no timeout dos testes para 20.000ms no `vite.config.ts`.

### 🚀 Novidades da Versão 1.0.7
- **Injeção Autônoma e Completa de Pixels de Conversão**:
  - Injeção dinâmica e automática dos SDKs oficiais das 3 plataformas líderes de tráfego pago:
    - **Meta Pixel (Facebook)**: Carregamento assíncrono oficial `fbevents.js`, inicialização com `fbq('init')` e disparo automático de `PageView`;
    - **Google Tag (Analytics & Google Ads)**: Injeção de `gtag/js?id=...`, inicialização de `window.dataLayer` e disparo automático do evento `config`;
    - **TikTok Pixel**: Instalação assíncrona oficial `events.js`, inicialização de métodos diferidos via `ttq.load()` e disparo de `ttq.page()`.
  - **Disparos em Tempo Real nos Marcos do Vídeo**:
    - Disparo de eventos aos **25%** (`percent_25`), **50%** (`percent_50`), **75%** (`percent_75`), **100%** (`percent_100`) e no momento exato do **Pitch de Vendas** (`pitch`).
    - Nomes de eventos customizáveis diretamente pelo painel do editor de vídeo.
    - Disparo direto nos SDKs dentro do player e retransmissão via `postMessage` (`VTURB_PIXEL_TRACK`) para a página de vendas externa.
  - **Suporte Autônomo no Código Embed de Landing Pages**:
    - O código gerado em `embedScriptGenerator` agora detecta se a landing page já possui os pixels instalados. Caso não possua, instala de forma transparente e autônoma os SDKs necessários, garantindo que o rastreamento funcione perfeitamente mesmo em páginas externas limpas.
- **Suíte de Testes Automatizados Expandida**:
  - 150 testes unitários frontend (Vitest) e 41 testes backend (Pytest) 100% aprovados.

### 🚀 Novidades da Versão 1.0.6
- **Modo "Apenas o Vídeo" (`transparent_background`)**:
  - Nova opção no painel de estilo para remover qualquer barra preta lateral/superior/inferior de padding ao redor do vídeo no container do player.
  - O container adapta-se diretamente à proporção exata da mídia, permitindo embeds perfeitos e sem bordas pretas em páginas de vendas externas.
- **Eliminação de tela branca nos primeiros segundos**:
  - Solução contra a transparência padrão do elemento `<video>` em HTML5 antes do buffering inicial.
  - Implementação de fundo sólido `#000000` durante o estado de carregamento (`!isVideoReady`) e transição suave para transparência assim que o primeiro frame é decodificado (`onLoadedData`/`readyState >= 2`).
  - Auto-poster nativo via `#t=0.001` adicionado à URL da mídia quando `thumbnail_url` não estiver definido, permitindo a prévia instantânea do primeiro frame sem flash branco.
  - Micro-spinner suave exibido durante o carregamento inicial.
- **Resiliência e Correção de Crash em Controles Customizados**:
  - Correção em `CustomPlayerControls.tsx` garantindo fallback seguro para `controls_config: null` sem quebra da renderização do componente.
- **Suíte de Testes Automatizados Expandida**:
  - 137 testes unitários frontend (Vitest) e 41 testes backend (Pytest) 100% aprovados.

### 🚀 Novidades da Versão 1.0.5
- **Eliminação de tela branca no Embed**: Script inline em `index.html` e tema dark garantido antes da renderização do bundle;
- **Compatibilidade Iframe & CSP**: Configuração Nginx com `Content-Security-Policy: frame-ancestors *;` para permitir incorporação em qualquer domínio;
- **Player Flutuante (Picture-in-Picture)**: Suporte completo tanto em páginas com o player incorporado diretamente quanto em iframes com script wrapper e `IntersectionObserver`;
- **Controles Customizados Dinâmicos**: Barra de progresso, botão de play, volume com slider e tempo do vídeo com respeito rigoroso às configurações de exibição/ocultação do painel.

