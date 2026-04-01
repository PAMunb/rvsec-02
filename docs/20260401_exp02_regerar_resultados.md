# Plano: Regerar Resultados do Experimento 02 (Novas Specs Genéricas)

**Data**: 2026-04-01
**Escopo**: Coletar, processar e organizar os resultados do Experimento 02 com as 27 novas specs genéricas
**Fora de escopo**: Integração com artigo journal, modificações no replication package

---

## Contexto

### Três Conjuntos de Especificações

| Conjunto | Qtd Specs | Origem | Referência |
|----------|-----------|--------|------------|
| **JCA** | 25 | Specs de criptografia (Java Cryptography Architecture) | Artigo ICST original |
| **Generic Original** | 120 | Mineradas automaticamente da Property Database | Artigo ICST original |
| **New Generic** | 27 | Selecionadas manualmente da Property Database | rvsec-02 (este projeto) |

### Estado Atual dos Dados (New Generic)

| Item | Exp01 | Exp02 |
|------|-------|-------|
| Execução | COMPLETA (jan/2026) | PARCIAL (03/fev/2026) — faltam ares e qtesting |
| APKs | 557 total, **349 instrumentados** | **10** APKs |
| Ferramentas | 11 | **5 de 7** executadas (faltam ares e qtesting) |
| Timeouts | 60, 120, 180, 300s | 10800s (3h) |
| Repetições | 3 | 1 |
| Execuções totais | 46.068 | 50 de 70 esperadas |
| Logcats brutos | gdrive/experiment01/ (61GB, 37 batches) | rvsec-02/exp02/containers/{01-05}/results/ |
| Planilhas processadas | gdrive/exp01_generic_planilhas/ (4 CSVs, já renomeados _new) | **NÃO PROCESSADO** |
| .methods | gdrive/all_methods/ (557 + mop_methods.csv) | Reutilizar do exp01 |
| Formato logcat | threadtime | threadtime |

### Ferramentas: Discrepância Identificada

O exp02 nos experimentos anteriores (JCA e generic original) usou **7 ferramentas**: ape, ares, droidbot_bfs_greedy, droidbot_dfs_greedy, fastbot, humanoid, qtesting. O CLAUDE.md documenta corretamente estas 7 ferramentas.

Porém, o `.env-exp02` e a `execution_memory.json` confirmam que **apenas 5 foram executadas**: ape, droidbot_bfs_greedy, droidbot_dfs_greedy, fastbot, humanoid. **Ares e qtesting não foram executadas.**

Ambas as ferramentas funcionaram normalmente no exp01 new generic (4.188 execuções cada, com 1.095 e 1.127 erros detectados respectivamente).

**Decisão**: Processar os resultados das 5 ferramentas já executadas. Planejar execução complementar de ares e qtesting (ver Fase A no final).

### Projetos Envolvidos

| Projeto | Path | Papel |
|---------|------|-------|
| **rvsec-02** | `/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-02` | Orquestração dos experimentos |
| **rvsec-regerar-resultados** | `/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-regerar-resultados` | Parser de logcats → CSVs |
| **gdrive** | `/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS` | Armazenamento final dos resultados |

### Convenção de Nomes

Para distinguir dos resultados do "generic original" (120 specs), todos os artefatos das novas specs genéricas (27 specs) usam o sufixo `_new`:

| Arquivo | Descrição |
|---------|-----------|
| `exp01_generic_new_summary.csv` | Exp01, 349 APKs, 11 tools (já renomeado) |
| `exp02_generic_new_summary.csv` | Exp02, 10 APKs, 5 tools (a gerar) |

---

## Tarefas

### Fase 1: Coleta dos resultados brutos do exp02

Os resultados do exp02 ainda estão nos containers do rvsec-02. Precisam ser copiados para o gdrive, seguindo a mesma estrutura do experiment01.

#### Tarefa 1.1: Verificar completude dos resultados brutos

**Objetivo**: Confirmar que todas as 50 execuções (10 APKs × 5 tools) geraram logcats e traces.

```bash
cd /pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-02

for c in 01 02 03 04 05; do
  echo "Container $c:"
  find exp02/containers/$c/results/20260203135648/ -name "*.logcat" | wc -l
  find exp02/containers/$c/results/20260203135648/ -name "*.trace" | wc -l
done
```

**Esperado**: 10 logcats + 10 traces por container, total 50+50.

#### Tarefa 1.2: Copiar resultados brutos para o gdrive

**Objetivo**: Consolidar em `gdrive/NOVAS_SPECS_GENERICAS/experiment02/`.

A estrutura deve espelhar o experiment01:

```
experiment01/                          experiment02/
├── batch-01/                          ├── 20260203135648/
│   ├── 20260101144516/                │   ├── com.blogspot.e_kanivets.moneytracker_38.apk/
│   │   ├── app.crescentcash.src/      │   │   ├── *.logcat (5 ferramentas)
│   │   │   ├── *.logcat               │   │   └── *.trace (5 ferramentas)
│   │   │   └── *.trace               │   ├── com.gianlu.dnshero_40.apk/
│   │   └── ...                        │   │   └── ...
│   ├── execution.log                  │   └── ... (10 APKs)
│   └── instrument_errors.json         ├── execution_memory.json (consolidado)
├── batch-02/                          └── .methods (10 arquivos)
│   └── ...
└── ...
```

**Diferença**: exp01 tem batches (37), exp02 tem apenas 1 timestamp (sem batches, sem execution.log).

```bash
GDRIVE="/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS"
RVSEC02="/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-02"
TIMESTAMP="20260203135648"

# Criar estrutura: experiment02/timestamp/apk/
mkdir -p $GDRIVE/experiment02/$TIMESTAMP

# Copiar resultados de cada container (os 5 containers → 1 diretório flat)
for c in 01 02 03 04 05; do
  for apk_dir in $RVSEC02/exp02/containers/$c/results/$TIMESTAMP/*/; do
    apk=$(basename "$apk_dir")
    echo "Copiando: container $c / $apk"
    cp -r "$apk_dir" "$GDRIVE/experiment02/$TIMESTAMP/$apk/"
  done
done

# Consolidar execution_memory de cada container
for c in 01 02 03 04 05; do
  cp $RVSEC02/exp02/containers/$c/results/$TIMESTAMP/execution_memory.json \
     $GDRIVE/experiment02/execution_memory_container_$c.json
done

# Copiar .methods dos 10 APKs (reutilizando do exp01)
for apk_dir in $GDRIVE/experiment02/$TIMESTAMP/*/; do
  apk=$(basename "$apk_dir")
  cp $GDRIVE/all_methods/${apk}.methods $GDRIVE/experiment02/$TIMESTAMP/$apk/ 2>/dev/null
done
```

#### Tarefa 1.3: Verificar integridade dos logcats copiados

```bash
# Verificar RVSEC-COV (cobertura) e RVSEC (violações) em cada logcat
for logcat in $GDRIVE/experiment02/$TIMESTAMP/*/*.logcat; do
  cov=$(grep -c "RVSEC-COV" "$logcat" 2>/dev/null)
  viol=$(grep -c "^.*V RVSEC   :" "$logcat" 2>/dev/null)
  echo "$(basename $logcat): $cov cov, $viol violations"
done

# Contagem total
echo "Total logcats:"
find $GDRIVE/experiment02/$TIMESTAMP -name "*.logcat" | wc -l   # Esperado: 50
echo "Total APKs:"
ls -d $GDRIVE/experiment02/$TIMESTAMP/*.apk | wc -l             # Esperado: 10
```

**Critério de aceite**: 50 logcats, 10 diretórios de APK, todos com RVSEC-COV > 0.

---

### Fase 2: Configurar rvsec-regerar-resultados

O parser precisa saber onde encontrar logcats, .methods e lista de APKs válidos.

#### Tarefa 2.1: Verificar lista de APKs válidos

```bash
cd /home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-regerar-resultados

# apks_exp02.txt já tem os mesmos 10 APKs (usados no JCA e generic original)
cat data/apks_exp02.txt
```

**Reutilizar** `apks_exp02.txt` — são os mesmos 10 APKs.

#### Tarefa 2.2: Adicionar configuração para GENERIC_NEW no config.py

**Arquivo**: `rvsec-regerar-resultados/config.py`

```python
# ============================
# NOVAS SPECS GENÉRICAS (27 specs - rvsec-02)
# ============================

GDRIVE_NEW_GENERIC = "/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS"

# Logcat directories - new generic
LOGCAT_EXP01_GENERIC_NEW_DIR = os.path.join(GDRIVE_NEW_GENERIC, "experiment01")
LOGCAT_EXP02_GENERIC_NEW_DIR = os.path.join(GDRIVE_NEW_GENERIC, "experiment02")

# All methods - new generic (reutiliza do exp01, gerado com as 27 specs)
ALL_METHODS_GENERIC_NEW = os.path.join(GDRIVE_NEW_GENERIC, "all_methods")

# Valid APKs - new generic
VALID_APKS_EXP01_GENERIC_NEW = os.path.join(PROJECT_ROOT, "data", "apks_exp01_generic_new.txt")
VALID_APKS_EXP02_GENERIC_NEW = VALID_APKS_EXP02  # Mesmos 10 APKs
```

#### Tarefa 2.3: Adicionar SpecType.GENERIC_NEW ao domain/models.py

```python
class SpecType(Enum):
    JCA = 1
    GENERIC = 2
    GENERIC_NEW = 3  # Novas specs genéricas (27 specs, rvsec-02)
```

#### Tarefa 2.4: Atualizar main.py para suportar GENERIC_NEW

Na função `_gerrate_report`, atualizar a seleção de all_methods:

```python
# Antes
all_methods_dir = config.ALL_METHODS_JCA if spec == SpecType.JCA else config.ALL_METHODS_GENERIC

# Depois
if spec == SpecType.JCA:
    all_methods_dir = config.ALL_METHODS_JCA
elif spec == SpecType.GENERIC_NEW:
    all_methods_dir = config.ALL_METHODS_GENERIC_NEW
else:
    all_methods_dir = config.ALL_METHODS_GENERIC
```

#### Tarefa 2.5: Adicionar combinação exp02 GENERIC_NEW ao AAA

```python
AAA.append({
    "exp": ExperimentType.EXP02,
    "spec": SpecType.GENERIC_NEW,
    "valid_apks_file": VALID_APKS_EXP02_GENERIC_NEW,
    "logcat_dir": LOGCAT_EXP02_GENERIC_NEW_DIR
})
```

**IMPORTANTE**: Para rodar APENAS exp02 new generic, comentar as outras combinações em AAA ou filtrar.

#### Tarefa 2.6: Verificar seleção do parser

O parser é selecionado por ExperimentType:
```python
parser = Exp01Parser(logcat_file) if exp == ExperimentType.EXP01 else Exp02Parser(logcat_file)
```

Para exp02 → Exp02Parser (threadtime, com timestamps). Correto.

**Nota para futuro**: O exp01 new generic também tem logcats threadtime, mas o código usaria Exp01Parser. Se precisarmos reprocessar exp01, ajustar esta lógica.

#### Tarefa 2.7: Criar lista de APKs válidos para exp01 new generic (referência futura)

```bash
cut -d',' -f1 /home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS/exp01_generic_planilhas/exp01_generic_new_summary.csv | \
  tail -n+2 | sort -u > data/apks_exp01_generic_new.txt

wc -l data/apks_exp01_generic_new.txt  # Esperado: 349
```

---

### Fase 3: Executar o parser para exp02 new generic

#### Tarefa 3.1: Teste com 1 APK (dry run)

Testar com hourlyreminder (tem violações conhecidas: TreeSet_Comparable, SortedSet_Comparable, Object_MonitorOwner).

```bash
cd /home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-regerar-resultados

# Mini lista
echo "com.github.axet.hourlyreminder_476.apk" > data/apks_exp02_generic_new_mini.txt

# Temporariamente usar mini lista no config
# VALID_APKS_EXP02_GENERIC_NEW = os.path.join(PROJECT_ROOT, "data", "apks_exp02_generic_new_mini.txt")

source venv/bin/activate  # ou o venv apropriado
python main.py
```

**Validar output**:
```bash
wc -l exp02_generic_new_summary.csv   # Esperado: 6 (header + 5 tools)
wc -l exp02_generic_new_errors.csv    # Esperado: > 1

# Verificar specs violadas
grep "TreeSet_Comparable\|SortedSet_Comparable\|Object_MonitorOwner" exp02_generic_new_errors.csv | head -3

# Verificar time > 0 (timestamps extraídos)
head -3 exp02_generic_new_errors.csv
```

#### Tarefa 3.2: Executar para todos os 10 APKs

```bash
# Restaurar config para lista completa
# VALID_APKS_EXP02_GENERIC_NEW = VALID_APKS_EXP02

python main.py
```

#### Tarefa 3.3: Validar resultados completos

```bash
echo "=== Summary ==="
wc -l exp02_generic_new_summary.csv    # Esperado: 51 (header + 10 APKs × 5 tools)
cut -d',' -f1 exp02_generic_new_summary.csv | tail -n+2 | sort -u | wc -l  # 10 APKs
cut -d',' -f4 exp02_generic_new_summary.csv | tail -n+2 | sort -u          # 5 tools

echo "=== Errors ==="
wc -l exp02_generic_new_errors.csv
cut -d',' -f6 exp02_generic_new_errors.csv | tail -n+2 | sort | uniq -c | sort -rn

echo "=== Coverage ==="
wc -l exp02_generic_new_coverage.csv

echo "=== Logcat ==="
wc -l exp02_generic_new_logcat.csv    # Esperado: 51
```

**Validação cruzada** (violações brutas conhecidas dos logcats):

| APK | Violações brutas | Specs esperadas |
|-----|-----------------|-----------------|
| hourlyreminder | ~26.956 | TreeSet_Comparable, SortedSet_Comparable, Object_MonitorOwner |
| fhem | ~898 | Object_MonitorOwner |
| lesserpad | ~372 | Object_MonitorOwner, Closeable_MeaninglessClose |
| Outros 7 | 0 | — |

---

### Fase 4: Copiar resultados processados para o gdrive

#### Tarefa 4.1: Copiar CSVs

```bash
REGEN="/home/pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-regerar-resultados"
GDRIVE="/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS"

mkdir -p $GDRIVE/exp02_generic_new_planilhas

cp $REGEN/exp02_generic_new_summary.csv   $GDRIVE/exp02_generic_new_planilhas/
cp $REGEN/exp02_generic_new_errors.csv    $GDRIVE/exp02_generic_new_planilhas/
cp $REGEN/exp02_generic_new_coverage.csv  $GDRIVE/exp02_generic_new_planilhas/
cp $REGEN/exp02_generic_new_logcat.csv    $GDRIVE/exp02_generic_new_planilhas/

ls -la $GDRIVE/exp02_generic_new_planilhas/
```

---

### Fase 5: Investigar os 19 APKs sem resultados (exp01)

**Contexto**: 557 APKs totais - 349 com resultados - 189 erros de instrumentação = 19 APKs sem explicação.

#### Tarefa 5.1: Identificar os 19 APKs

```bash
cd /pedro/desenvolvimento/workspaces/workspaces-doutorado/workspace-rv/rvsec-02

# Todos os 557
ls /home/pedro/desenvolvimento/RV_ANDROID/NOVO/APKS/*.apk | xargs -n1 basename | sort > /tmp/all_557.txt

# 349 com resultados
cut -d',' -f1 /home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS/exp01_generic_planilhas/exp01_generic_new_summary.csv | \
  tail -n+2 | sort -u > /tmp/with_results_349.txt

# 189 com erro de instrumentação
python3 -c "
import json
with open('/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS/instrument/exp01_generic_instrument_errors.json') as f:
    data = json.load(f)
for apk in sorted(data.keys()):
    print(apk)
" > /tmp/instrument_errors_189.txt

# Os sem explicação
comm -23 /tmp/all_557.txt /tmp/with_results_349.txt > /tmp/without_results_208.txt
comm -23 /tmp/without_results_208.txt /tmp/instrument_errors_189.txt > /tmp/unexplained_19.txt

cat /tmp/unexplained_19.txt
```

#### Tarefa 5.2: Verificar logcats e traces nos resultados brutos

```bash
GDRIVE_EXP01="/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS/experiment01"

while read apk; do
  logcats=$(find $GDRIVE_EXP01 -path "*/$apk/*.logcat" 2>/dev/null | wc -l)
  traces=$(find $GDRIVE_EXP01 -path "*/$apk/*.trace" 2>/dev/null | wc -l)
  batch=$(grep "$apk" APKs.csv 2>/dev/null | cut -d',' -f2)
  echo "$apk: batch=$batch, $logcats logcats, $traces traces"
done < /tmp/unexplained_19.txt
```

**Possíveis causas**: APK sem .methods, instrumentação silenciosamente falha, APK não na lista válida usada pelo parser.

#### Tarefa 5.3: Documentar resultados

Criar seção em CLAUDE.md ou documento separado com lista e causa de cada APK.

---

### Fase 6: Atualizar CLAUDE.md

#### Tarefa 6.1: Documentar a discrepância de ferramentas do exp02

O CLAUDE.md lista corretamente 7 ferramentas (consistente com exp02 JCA e generic original). A execução real teve apenas 5. Adicionar nota explicativa:

```markdown
### Experimento 02: Execução Longa
- **APKs**: 10 (selecionados — mesmos do exp02 JCA/generic original)
- **Ferramentas (7)**: ape, ares, droidbot_bfs_greedy, droidbot_dfs_greedy, fastbot, humanoid, qtesting
- **Timeout**: 10800 segundos (3 horas)
- **Repetições**: 1

> **NOTA**: A execução inicial (03/fev/2026) incluiu apenas 5 ferramentas
> (ape, droidbot_bfs_greedy, droidbot_dfs_greedy, fastbot, humanoid).
> Ares e qtesting precisam ser executadas separadamente para completar
> o experimento. Ver Fase A do plano docs/20260401_exp02_regerar_resultados.md.
```

#### Tarefa 6.2: Adicionar seção de resultados processados

```markdown
## Resultados Processados

### Localização (gdrive)
- **Diretório base**: `/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS`
- **Exp01 planilhas**: `exp01_generic_planilhas/` (renomeados com sufixo _new)
- **Exp02 planilhas**: `exp02_generic_new_planilhas/` (5 de 7 ferramentas)
- **Resultados brutos**: `experiment01/` (37 batches), `experiment02/` (10 APKs)
- **All methods**: `all_methods/` (557 + mop_methods.csv)

### Convenção de Nomes
- Sufixo `generic_new` para distinguir das generic original (120 specs)
```

---

### Fase 7: Verificação final

#### Tarefa 7.1: Checklist de consistência

```bash
GDRIVE="/home/pedro/desenvolvimento/RV_ANDROID_NOVO/gdrive/NOVAS_SPECS_GENERICAS"

echo "=== VERIFICAÇÃO FINAL ==="

# 1. Exp01 planilhas (já renomeadas)
echo "1. Exp01 planilhas:"
ls $GDRIVE/exp01_generic_planilhas/exp01_generic_new_*.csv 2>/dev/null | wc -l  # 4

# 2. Exp02 planilhas (novas)
echo "2. Exp02 planilhas:"
ls $GDRIVE/exp02_generic_new_planilhas/exp02_generic_new_*.csv 2>/dev/null | wc -l  # 4

# 3. Exp02 resultados brutos
echo "3. Exp02 resultados brutos:"
ls -d $GDRIVE/experiment02/20260203135648/*.apk 2>/dev/null | wc -l  # 10

# 4. Contagens
echo "4. Contagens:"
wc -l $GDRIVE/exp01_generic_planilhas/exp01_generic_new_summary.csv  # 46069
wc -l $GDRIVE/exp02_generic_new_planilhas/exp02_generic_new_summary.csv  # 51

# 5. APKs únicos
echo "5. APKs:"
cut -d',' -f1 $GDRIVE/exp01_generic_planilhas/exp01_generic_new_summary.csv | tail -n+2 | sort -u | wc -l  # 349
cut -d',' -f1 $GDRIVE/exp02_generic_new_planilhas/exp02_generic_new_summary.csv | tail -n+2 | sort -u | wc -l  # 10

# 6. Tools no exp02
echo "6. Tools exp02:"
cut -d',' -f4 $GDRIVE/exp02_generic_new_planilhas/exp02_generic_new_summary.csv | tail -n+2 | sort -u  # 5 tools

# 7. Time column
echo "7. Time (exp02 errors):"
head -2 $GDRIVE/exp02_generic_new_planilhas/exp02_generic_new_errors.csv
```

#### Tarefa 7.2: Estrutura final no gdrive

```
NOVAS_SPECS_GENERICAS/
├── experiment01/                       # Resultados brutos exp01 (37 batches, 61GB)
├── experiment02/                       # Resultados brutos exp02 (10 APKs)         ← NOVO
│   ├── 20260203135648/                 #   Timestamp da execução
│   │   ├── {apk_name}/                #   10 diretórios, cada um com 5 logcats + 5 traces
│   │   └── ...
│   └── execution_memory_container_*.json
├── exp01_generic_planilhas/            # Planilhas exp01 (renomeados _new)          ← JÁ FEITO
│   ├── exp01_generic_new_summary.csv   #   46069 linhas, 349 APKs, 11 tools
│   ├── exp01_generic_new_errors.csv    #   13285 linhas, 14 specs violadas
│   ├── exp01_generic_new_coverage.csv  #   ~3.5M linhas
│   └── exp01_generic_new_logcat.csv    #   46069 linhas
├── exp02_generic_new_planilhas/        # Planilhas exp02 (novas)                    ← NOVO
│   ├── exp02_generic_new_summary.csv   #   51 linhas, 10 APKs, 5 tools (parcial)
│   ├── exp02_generic_new_errors.csv    #   com coluna time (análise temporal)
│   ├── exp02_generic_new_coverage.csv  #   com coluna time
│   └── exp02_generic_new_logcat.csv    #   51 linhas
├── all_methods/                        # .methods (557 APKs + mop_methods.csv)
├── instrument/                         # Erros de instrumentação (189 APKs)
├── specs/                              # 27 specs MOP
└── all_methods.zip, instrument.zip     # Backups comprimidos
```

---

## Ordem de Execução

```
Fase 1 (Coleta) ──► Fase 2 (Config parser) ──► Fase 3 (Executar parser) ──► Fase 4 (Copiar gdrive)
                                                                                      │
Fase 5 (Investigar 19 APKs) ──── (independente, paralela) ───────────────────────────┤
Fase 6 (Atualizar CLAUDE.md) ─── (independente, paralela) ───────────────────────────┤
                                                                                      │
Fase 7 (Verificação final) ◄─────────────────────────────────────────────────────────┘
```

---

## Fase A: Execução Complementar — Ares e QTesting (Pré-Planejamento)

### Contexto

O exp02 deveria usar as mesmas 7 ferramentas dos exp02 anteriores (JCA e generic original). A execução de 03/fev/2026 incluiu apenas 5. Faltam **ares** e **qtesting** para os mesmos 10 APKs com timeout de 3 horas.

### Configuração

| Parâmetro | Valor |
|-----------|-------|
| APKs | 10 (mesmos) |
| Ferramentas | **ares, qtesting** |
| Timeout | 10800s (3h) |
| Repetições | 1 |
| Execuções | 20 (10 APKs × 2 tools) |
| Specs | 27 novas generic (mesmas) |

### Preparação

#### A.1: Criar .env para execução complementar

```bash
# exp02/.env-exp02-complementar
REPETITIONS=1
TIMEOUTS=10800
TOOLS=ares qtesting
HUMANOID_URL=rv-humanoid:50405
NO_WINDOW=true
JCA_SPEC=false
CPUS=8
MEMORY=16g
```

#### A.2: Configurar containers

Os APKs já estão instrumentados nos containers. As specs já estão copiadas. Precisamos apenas:

1. Verificar que os APKs instrumentados ainda estão em `exp02/containers/{01-05}/instrumented/`
2. Verificar que as specs estão em `exp02/containers/{01-05}/specs/`
3. Criar docker-compose com as 2 ferramentas novas

**ATENÇÃO**: Ares precisa do humanoid service (`rv-humanoid:50405`). Qtesting não depende do humanoid.

#### A.3: Criar docker-compose para execução complementar

```yaml
# exp02/docker-compose-exp02-complementar.yml
# Mesmo formato do docker-compose-exp02.yml, alterando:
# - TOOLS=ares qtesting
# - Manter mesmos volumes (APKs instrumentados, specs, results)
# - Adicionar RV_SKIP_INSTRUMENT=true (APKs já instrumentados)
# - Adicionar RV_SKIP_MONITORS=true (monitores já gerados)
```

**Ponto crítico**: Os resultados devem ir para o MESMO diretório timestamp? Ou um novo?
- **Opção A**: Novo timestamp → resultados separados, merge manual depois
- **Opção B**: Mesmo timestamp → se o container aceitar, os resultados ficam junto

Provavelmente **Opção A** é mais segura. Depois de coletar, os logcats podem ser copiados para o mesmo diretório no gdrive.

#### A.4: Estimativa de tempo

- 10 APKs × 2 tools × 3h = 60 horas sequenciais
- Com 5 containers (2 APKs cada): ~12 horas
- Ares pode travar em alguns APKs (histórico de bugs no exp01)

#### A.5: Pós-execução

1. Coletar logcats para `gdrive/experiment02/{novo_timestamp}/`
2. Copiar logcats para junto dos existentes (mesmo diretório de APK)
3. Reprocessar com parser (agora com 7 tools)
4. Atualizar planilhas: summary terá 71 linhas (10 × 7 + header)

### Decisão pendente

- Quando executar (prioridade vs recursos disponíveis)
- Se deve usar `RV_MEMORY_FILE` para skip de tarefas já executadas
- Se deve montar watchdog para ares (histórico de travamentos)

---

## Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Parser falha com formato threadtime | CSVs não gerados | Teste com 1 APK (Tarefa 3.1) |
| Logcats corrompidos/truncados | Violações perdidas | Verificar RVSEC-COV (Tarefa 1.3) |
| Naming collision no gdrive | Sobrescrever dados | Sufixo `_new`, diretórios separados |
| config.py com estado sujo | Reprocessar errado | Backup antes de modificar; AAA seletivo |
| Ares trava na execução complementar | Execução incompleta | Watchdog + resume, conforme exp01 |

---

## Referências

- **Parser exp02**: `rvsec-regerar-resultados/parsers/exp02_parser.py`
- **Config parser**: `rvsec-regerar-resultados/config.py`
- **Docs exp02**: `rvsec-02/docs/experimento_02.md`
- **Exp02 antigo (JCA)**: `ase-journal/dataset/results/summary/exp02_jca_summary.csv`
- **Exp02 antigo (generic)**: `ase-journal/dataset/results/summary/exp02_generic_summary.csv`
- **Artigo**: `ase-journal/main-icst.pdf`
