# RVSec-02: Experimentos com Generic Specs

## Contexto do Projeto

Este projeto orquestra a execução de experimentos de **Runtime Verification (RV)** em aplicações Android usando Docker Compose. O objetivo é detectar violações de especificações de API em tempo de execução, utilizando ferramentas de geração automática de testes.

### Artigo de Referência

O experimento replica e estende o estudo publicado no artigo:
- **Título**: "On the Effectiveness of Integrating Android Test-Case Generation with Runtime Verification for Detecting Cryptographic API Misuses"
- **PDF**: `/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/ase-journal/main-icst.pdf`

## Especificações (Specs)

### Generic Specs (27 specs) - NOVO EXPERIMENTO

Localizadas em `./specs/`, estas especificações foram selecionadas da Property Database:
- **Fonte**: https://www.cs.cornell.edu/~legunsen/spec-eval/
- **Categorização**: https://github.com/ncsu-swat/rvprio

**Distribuição por severidade**:
- ERROR (17): Bugs verdadeiros que causam exceções ou comportamento incorreto
- WARNING (8): Potenciais problemas de código
- SUGGESTION (2): Melhorias de código

**Lista das specs**:
```
CharSequence_NotInSet.mop
CharSequence_UndefinedHashCode.mop
Closeable_MeaninglessClose.mop
Collection_HashCode.mop
Collection_UnsynchronizedAddAll.mop
Collections_SynchronizedCollection.mop
Collections_SynchronizedMap.mop
Collections_UnnecessaryNewSetFromMap.mop
Comparable_CompareToNull.mop
Comparable_CompareToNullException.mop
InputStream_ManipulateAfterClose.mop
ListIterator_Set.mop
Long_BadParsingArgs.mop
Map_UnsafeIterator.mop
Object_MonitorOwner.mop
OutputStream_ManipulateAfterClose.mop
Reader_ManipulateAfterClose.mop
Serializable_NoArgConstructor.mop
ServerSocket_Backlog.mop
ServerSocket_SetTimeoutBeforeBlocking.mop
SortedSet_Comparable.mop
TreeMap_Comparable.mop
TreeSet_Comparable.mop
URLConnection_OverrideGetPermission.mop
URLDecoder_DecodeUTF8.mop
URLEncoder_EncodeUTF8.mop
Writer_ManipulateAfterClose.mop
```

## APKs

- **Localização**: `/home/pedro/desenvolvimento/RV_ANDROID/NOVO/APKS`
- **Quantidade**: 557 APKs do F-Droid
- **Taxa de instrumentação esperada**: ~65% (~362 APKs)
- **Pacotes diferentes**: 138 APKs (24.8%) têm manifest_package ≠ detected_package

## Abordagem de Execução: Batches Dinâmicos

### Conceito

```
557 APKs → 37 batches (15-16 APKs cada) → 7 containers independentes
```

Cada container processa batches sequencialmente. Quando termina um batch, é reconfigurado para o próximo disponível, sem afetar os outros containers.

### Vantagens

- **Sem ociosidade**: Container terminou → pega próximo batch
- **Balanceamento**: Containers rápidos processam mais batches
- **Isolamento**: Reinicia só 1 container, outros continuam
- **Recuperação**: Se travar, afeta apenas 15 APKs

### Fluxo

```
Início:
├── Container 01 → Batch 01
├── Container 02 → Batch 02
├── Container 03 → Batch 03
├── Container 04 → Batch 04
├── Container 05 → Batch 05
├── Container 06 → Batch 06
└── Container 07 → Batch 07

Container 01 termina → reconfigura para Batch 08
Container 03 termina → reconfigura para Batch 09
...
```

## Experimentos

### Experimento 01: Execução Completa
- **APKs**: 557 candidatos, **349 instrumentados** (189 erros de instrumentação, 19 descartados)
- **Ferramentas (11)**: ape, ares, droidbot, droidbot_bfs_greedy, droidbot_bfs_naive, droidbot_dfs_greedy, droidmate, fastbot, humanoid, monkey, qtesting
- **Timeouts (4)**: 60, 120, 180, 300 segundos
- **Repetições**: 3
- **Total**: 46.068 execuções (349 APKs × 132)
- **Status**: COMPLETO (jan/2026)

### Experimento 02: Execução Longa
- **APKs**: 10 (mesmos do exp02 JCA/generic original)
- **Ferramentas (7)**: ape, ares, droidbot_bfs_greedy, droidbot_dfs_greedy, fastbot, humanoid, qtesting
- **Timeout**: 10800 segundos (3 horas)
- **Repetições**: 1
- **Total**: 70 execuções (10 APKs × 7 tools)
- **Status**: COMPLETO (fev-abr/2026 — execução inicial com 5 tools em fev, complementar ares+qtesting em abr)

### APKs sem resultados (19 de 557)

| Categoria | APKs | Causa |
|-----------|------|-------|
| `.methods` vazio | 16 | Análise estática sem métodos (game engines, packages incompatíveis) |
| Sem logcats | 2 | Falha/perda na execução |
| Sem nada | 1 | Erro de instrumentação não registrado |

## Resultados Processados

### Localização (gdrive)
- **Diretório base**: `/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS`
- **Exp01 planilhas**: `exp01_generic_planilhas/` (4 CSVs com sufixo `_new`)
- **Exp02 planilhas**: `exp02_generic_new_planilhas/` (4 CSVs)
- **Resultados brutos**: `experiment01/` (37 batches), `experiment02/` (10 APKs × 7 tools)
- **All methods**: `all_methods/` (557 + mop_methods.csv)
- **Erros de instrumentação**: `instrument/exp01_generic_instrument_errors.json`

### Convenção de Nomes
Sufixo `generic_new` para distinguir das generic original (120 specs):
- `exp01_generic_new_summary.csv` — 349 APKs, 11 tools
- `exp02_generic_new_summary.csv` — 10 APKs, 7 tools

### Plano de Processamento
Ver `docs/20260401_exp02_regerar_resultados.md` para detalhes completos.

## Ambiente Python

**IMPORTANTE**: Sempre usar o venv do projeto para executar scripts Python:

```bash
# Ativar venv
source ./venv/bin/activate

# Ou executar diretamente
./venv/bin/python script.py
```

**Nota**: `/home/pedro/desenvolvimento` é um link simbólico para `/pedro/desenvolvimento`.

### Dependências

```
rich
pandas
openpyxl
androguard==3.4.0a1  # Versão específica para análise de APKs
networkx
```

Instalar: `./venv/bin/pip install -r requirements.txt`

## Estrutura do Projeto

```
rvsec-02/
├── specs/                      # 27 Generic Specs (.mop files)
├── batches/                    # APKs organizados por batch
│   ├── 01/                     # 15 APKs
│   ├── 02/                     # 15 APKs
│   ├── ...
│   ├── 36/                     # 16 APKs
│   └── 37/                     # 16 APKs
├── containers/                 # Dados de execução por container
│   ├── 01/
│   │   ├── instrumented/       # APKs instrumentados
│   │   ├── results/            # Resultados
│   │   └── specs/              # Cópia das specs
│   ├── 02/ ... 07/
├── results/                    # Resultados consolidados
│   ├── batch-01/               # Diretório do batch
│   │   ├── YYYYMMDDHHMMSS/     # Timestamp com resultados
│   │   ├── execution.log       # Log do container
│   │   └── instrument_errors.json  # Erros de instrumentação
│   ├── batch-01.zip            # ZIP do batch
│   └── ...
├── tools/                      # JARs auxiliares
│   ├── methods-extractor.jar   # Extrai métodos do APK via Soot
│   └── mop-extractor.jar       # Extrai métodos das specs MOP
├── scripts/                    # Scripts Python
│   ├── config.py               # Configurações de paths
│   └── all_methods/            # Pacote para geração de .methods
│       ├── novo.py             # Gerador de .methods (single APK)
│       ├── batch_generator.py  # Gerador paralelo (todos APKs)
│       └── package_detector.py # Detector de package name
├── all_methods/                # Output: arquivos .methods gerados (557)
├── mini-exp-01/ a 05/          # Mini-experimentos de validação
├── APKs.csv                    # Metadados dos APKs
├── BATCHES.csv                 # Controle de execução dos batches
├── docker-compose.yml          # Orquestração principal
├── .env                        # Variáveis de ambiente
├── venv/                       # Ambiente virtual Python
├── requirements.txt            # Dependências Python
└── CLAUDE.md                   # Este arquivo
```

## Planilhas CSV

### APKs.csv

| Coluna | Descrição |
|--------|-----------|
| apk | Nome do arquivo APK |
| batch | Número do batch (01-37) |
| instrumented | Se foi instrumentado com sucesso |
| methods_count | Quantidade de métodos no .methods |
| methods_empty | Se o .methods está vazio |
| manifest_package | Pacote do AndroidManifest.xml |
| detected_package | Pacote detectado pela heurística |

### BATCHES.csv

| Coluna | Descrição |
|--------|-----------|
| batch | Número do batch (01-37) |
| apks_total | Total de APKs no batch |
| apks_instrumented | APKs instrumentados no batch |
| container | Container atribuído (01-07) |
| status | pending, running, completed |
| start | Timestamp de início |
| end | Timestamp de término |

## Configuração Docker

### Imagem
- `phtcosta/rvandroid:0.0.1` - Container com RV4Android
- `phtcosta/humanoid:1.0` - Serviço de automação UI

### Variáveis de Ambiente Importantes

| Variável | Descrição |
|----------|-----------|
| `RV_REPETITIONS` | Número de repetições |
| `RV_TIMEOUTS` | Lista de timeouts em segundos |
| `RV_TOOLS` | Ferramentas de teste (separadas por espaço) |
| `RV_JCA_SPEC` | `true` para JCA Specs, `false` para Generic Specs |
| `RV_MEMORY_FILE` | Caminho para execution_memory.json (para resume) |
| `RV_SKIP_MONITORS` | `true` para pular geração de monitores |
| `RV_SKIP_INSTRUMENT` | `true` para pular instrumentação |
| `RV_SKIP_STATIC_ANALYSIS` | `true` para pular análise estática |

### Montagem das Generic Specs

Para usar as Generic Specs em vez das JCA Specs, montar o volume:
```yaml
volumes:
  - ./containers/XX/specs:/opt/rvsec/rvsec/rvsec-mop/src/main/resources/generic/
```

E definir `RV_JCA_SPEC=false` no .env.

## Procedimentos de Execução

### Monitoramento

```bash
# Monitor visual
python monitor.py containers --prefix rv

# Watchdog com auto-resume (recomendado)
nohup python watchdog.py containers --prefix rv --interval 10 &
tail -f watchdog.log
```

### Quando um Container Termina (100%)

```bash
BATCH=XX
CONTAINER=XX

# 1. Parar
docker stop rv-$CONTAINER

# 2. Identificar timestamp
TIMESTAMP=$(ls containers/$CONTAINER/results/ | grep -E "^[0-9]+$" | head -1)

# 3. Criar diretório de resultados
mkdir -p results/batch-$BATCH

# 4. Copiar resultados
cp -r containers/$CONTAINER/results/$TIMESTAMP results/batch-$BATCH/
docker logs rv-$CONTAINER > results/batch-$BATCH/execution.log 2>&1
cp containers/$CONTAINER/instrumented/instrument_errors.json results/batch-$BATCH/ 2>/dev/null

# 5. Criar ZIP
cd results && zip -r batch-$BATCH.zip batch-$BATCH/ && cd ..

# 6. Atualizar BATCHES.csv (completed)

# 7. Limpar
rm -rf containers/$CONTAINER/{results,instrumented}/*

# 8. Editar docker-compose.yml (próximo batch + remover resume config)

# 9. Atualizar BATCHES.csv (novo batch running)

# 10. Reiniciar
docker compose up -d rv$CONTAINER
```

### Resume (Container Travado)

> **NOTA**: O watchdog.py automatiza este processo.

```bash
CONTAINER=XX
TIMESTAMP=$(ls containers/$CONTAINER/results/ | grep -E "^[0-9]+$" | head -1)

docker stop rv-$CONTAINER
```

Adicionar ao docker-compose.yml:
```yaml
- RV_MEMORY_FILE=/opt/rvsec/rv-android/results/$TIMESTAMP/execution_memory.json
- RV_SKIP_INSTRUMENT=true
- RV_SKIP_MONITORS=true
- RV_SKIP_STATIC_ANALYSIS=true
```

**IMPORTANTE**: Sempre recriar o container do zero (stop + rm + up), não apenas reiniciar:
```bash
docker stop rv-$CONTAINER && docker rm rv-$CONTAINER && docker compose up -d rv$CONTAINER
```

Usar apenas `docker compose up -d` pode não funcionar corretamente (emulador não inicia, CPU/RAM baixos).

## Documentação

- **Plano de Execução**: `./docs/20251231_plano.md` - Guia prático de execução
- **Pré-Plano (Validação)**: `./docs/20251231_pre_plano.md` - Mini-experimentos e validações

## Pós-Experimento: Regeneração de Resultados

> **IMPORTANTE**: A imagem Docker NÃO será modificada. Os resultados serão regenerados offline usando parser externo.

### Parser para Generic Specs

O parser interno da imagem tem limitações com o formato das Generic Specs. Usaremos um parser externo:

**Localização**: `/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-regerar-resultados/parsers/exp02_parser.py`

**Formatos de Log Suportados**:
- **RVSEC (Violações)**: `class.method(file:line) ::: SpecName went into an error state.`
- **RVSEC-COV (Cobertura)**: `class:::method:::(params)` ou `<class: returnType method(params)>`

### Geração de .methods (Reachability Analysis)

**Scripts locais** (adaptados de rvsec-regerar-resultados):

```bash
# Gerar .methods para um APK específico
cd scripts
../venv/bin/python -m all_methods.novo nome_do_apk.apk

# Gerar .methods para todos os 557 APKs (paralelo)
cd scripts
../venv/bin/python -m all_methods.batch_generator --all --batch-size 5

# Modo teste (10 APKs)
../venv/bin/python -m all_methods.batch_generator --test
```

**Colunas do CSV .methods**:
- `class`: Nome da classe
- `method`: Nome do método
- `parameters`: Parâmetros do método
- `signature`: Assinatura completa
- `is_activity`: Se a classe é uma Activity
- `reachable`: Método alcançável a partir de entrypoints
- `reaches_mop`: Método alcança métodos monitorados pelas specs
- `directly_reaches_mop`: Método chama diretamente métodos monitorados
- `androguard`: Método encontrado no call graph do Androguard

### Projeto de Referência (Regeneração)

**Localização**: `/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-regerar-resultados/`

```
rvsec-regerar-resultados/
├── parsers/exp02_parser.py    # Parser para Generic Specs
├── all_methods/novo.py        # Script original de reachability
├── generators/                # Geradores de CSVs
└── docs/                      # Documentação (ATENÇÃO: maioria antiga, verificar código)
```

**Uso**: `./venv/bin/python main.py`

## Links Úteis

- Property Database: https://www.cs.cornell.edu/~legunsen/spec-eval/
- RVPrio: https://github.com/ncsu-swat/rvprio
- Projeto de seleção de specs: `/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-generic-specs/`
- Projeto de regeneração: `/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-regerar-resultados/`
