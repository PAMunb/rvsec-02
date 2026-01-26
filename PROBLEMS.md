# Problemas Encontrados no Experimento

Este documento registra problemas encontrados durante a execução do experimento com Generic Specs.

---

## 1. APK cf.playhi.freezeyou_151.apk + ares

**Container**: 02 (batch 02)
**Data**: 2026-01-02 e 2026-01-03

### Descrição

O APK `cf.playhi.freezeyou_151.apk` combinado com a ferramenta `ares` causa travamento do container em todos os timeouts e repetições testados.

### Sintomas

- Container congela após o timeout do ares
- CPU cai para ~20-30%
- Processos zombie do emulador podem aparecer (nem sempre)
- Logs param de ser gerados (0 linhas nos últimos 10 minutos)
- Arquivos .logcat e .trace são criados

### Erro no Trace

O arquivo `.trace` contém o erro:
```
Starting training from zero
Using cpu device
Wrapping the env in a DummyVecEnv.
cannot unpack non-iterable NoneType object
```

Este é um **bug no próprio ares** - um erro Python interno que ocorre ao processar este APK específico.

### Tasks Afetadas

| Repetição | Timeout | Status |
|-----------|---------|--------|
| 1 | 60s | Executado normalmente |
| 1 | 120s | Travou - marcado manualmente |
| 1 | 180s | Travou - marcado manualmente |
| 1 | 300s | Travou - marcado manualmente |
| 2 | 60s | Executado normalmente |
| 2 | 120s | Travou - marcado manualmente |
| 2 | 180s | Travou - marcado manualmente |
| 2 | 300s | Travou - marcado manualmente |
| 3 | 60s | Travou - marcado manualmente |
| 3 | 120s | Travou - marcado manualmente |
| 3 | 180s | Travou - marcado manualmente |
| 3 | 300s | Travou - marcado manualmente |

### Solução Aplicada

Tasks problemáticas foram marcadas manualmente como executadas via:
```bash
docker exec rv-02 python3 -c "
import json
file_path = '/opt/rvsec/rv-android/results/TIMESTAMP/execution_memory.json'
with open(file_path, 'r') as f:
    mem = json.load(f)
mem['cf.playhi.freezeyou_151.apk']['REP']['TIMEOUT']['ares']['executed'] = True
with open(file_path, 'w') as f:
    json.dump(mem, f, indent=2)
"
```

Container recriado após cada intervenção.

### Arquivos Gerados

Os arquivos .logcat e .trace foram criados antes do travamento, porém com tamanho reduzido:
- `.logcat`: ~50-60 bytes
- `.trace`: ~140-270 bytes

### Análise

O ares parece ter problemas específicos com este APK. Possíveis causas:
- APK tem comportamento que confunde o ares
- Timeout do ares não é respeitado corretamente
- Problema de interação entre ares e o emulator

---

## 2. APK com.halftough.webcomreader_4.apk + qtesting

**Container**: 01 (batch 08)
**Data**: 2026-01-03

### Descrição

O APK `com.halftough.webcomreader_4.apk` combinado com a ferramenta `qtesting` causou travamento do container.

### Sintomas

- Container congela após o timeout
- CPU cai para ~15%
- Logs param de ser gerados (0 linhas nos últimos 5 minutos)
- Arquivos .logcat e .trace são criados com tamanho razoável

### Tasks Afetadas

| Repetição | Timeout | Status |
|-----------|---------|--------|
| 1 | 300s | Travou - marcado manualmente |

### Arquivos Gerados

- `.logcat`: 24323 bytes
- `.trace`: 32905 bytes

### Solução Aplicada

Task marcada manualmente como executada e container recriado.

### Análise

Problema pontual com qtesting neste APK específico. Diferente do problema com ares, este parece ser um caso isolado.

---

## 3. APK com.lithium.leona.openstud_190.apk + ares

**Container**: 03 (batch 09)
**Data**: 2026-01-05 e 2026-01-06

### Descrição

O APK `com.lithium.leona.openstud_190.apk` combinado com a ferramenta `ares` causa travamento do container em múltiplas repetições e timeouts.

### Sintomas

- Container congela após ares iniciar
- CPU cai para ~25%
- Logs param de ser gerados (0 linhas nos últimos 5 minutos)
- Arquivos .logcat e .trace são criados

### Erro no Trace (a partir de rep=2, timeout=180)

```
Starting training from zero
Using cpu device
Wrapping the env in a DummyVecEnv.
cannot unpack non-iterable NoneType object
```

Este é o **mesmo bug do problema #1** - erro interno do ares.

### Tasks Afetadas

| Repetição | Timeout | Status |
|-----------|---------|--------|
| 1 | 60s | Executado normalmente |
| 1 | 120s | Travou - marcado manualmente |
| 2 | 180s | Travou - marcado manualmente (2026-01-06 00:27) |
| 2 | 300s | Travou - marcado manualmente (2026-01-06 03:38) |

### Arquivos Gerados

- rep=1, timeout=120: `.logcat`: 58 bytes, `.trace`: 146 bytes
- rep=2, timeout=180: `.logcat`: 3905 bytes, `.trace`: 277 bytes (com erro Python)
- rep=2, timeout=300: `.logcat`: 13450 bytes, `.trace`: 481 bytes (com erro Python)

### Solução Aplicada

Tasks marcadas manualmente como executadas e container recriado (stop + rm + up).

### Análise

Mesmo problema do #1 (cf.playhi.freezeyou). O ares tem um bug interno que ocorre com certos APKs, causando erro "cannot unpack non-iterable NoneType object". O travamento ocorre porque o ares não trata corretamente este erro e o container fica aguardando indefinidamente.

---

## 4. APK com.lostrealm.lembretes_93.apk + ares

**Container**: 03 (batch 09)
**Data**: 2026-01-06

### Descrição

O APK `com.lostrealm.lembretes_93.apk` combinado com a ferramenta `ares` causa travamento do container devido a erro do Appium ao iniciar o aplicativo.

### Sintomas

- Container congela após ares iniciar
- CPU cai para ~20%
- Logs param de ser gerados (0 linhas nos últimos 5 minutos)
- Arquivos .logcat e .trace são criados

### Erro no Trace

```
Cannot start the 'com.lostrealm.lembretes' application.
Original error: '*' or 'com.lostrealm.lembretes.*' never started.
```

Este é um erro do **Appium** - o aplicativo não consegue ser iniciado pelo framework de automação usado pelo ares.

### Tasks Afetadas

| Repetição | Timeout | Status |
|-----------|---------|--------|
| 1 | 300s | Travou - marcado manualmente (2026-01-06 10:13) |
| 3 | 180s | Travou - marcado manualmente (2026-01-06 19:24) |
| 3 | 300s | Travou - marcado manualmente (2026-01-06 21:46) |

### Arquivos Gerados

- rep=1, timeout=300: `.logcat`: 78539 bytes, `.trace`: 1448 bytes (com erro Appium)
- rep=3, timeout=180: `.logcat`: 78539 bytes, `.trace`: 1448 bytes (com erro Appium)
- rep=3, timeout=300: `.logcat`: 78539 bytes, `.trace`: 1448 bytes (com erro Appium)

### Solução Aplicada

Task marcada manualmente como executada e container recriado (stop + rm + up).

### Análise

Diferente dos problemas #1 e #3 (erro interno do ares), este é um problema de compatibilidade entre o APK e o Appium. O aplicativo não inicia corretamente quando automatizado pelo ares/Appium, possivelmente devido a:
- Activity principal não detectada corretamente
- Permissões ou configurações especiais do APK
- Incompatibilidade com o emulador

---

## 5. APK com.saverio.wordoftheday_en_15.apk + ares

**Container**: 07 (batch 12)
**Data**: 2026-01-07

### Descrição

O APK `com.saverio.wordoftheday_en_15.apk` combinado com a ferramenta `ares` causa travamento do container devido ao mesmo bug interno do ares observado nos problemas #1 e #3.

### Sintomas

- Container congela após ares iniciar
- CPU cai para ~123%
- Memória muito baixa (~489MB)
- Logs param de ser gerados
- Arquivos .logcat e .trace são criados

### Erro no Trace

```
Starting training from zero
Using cpu device
Wrapping the env in a DummyVecEnv.
cannot unpack non-iterable NoneType object
```

Este é o **mesmo bug dos problemas #1 e #3** - erro interno do ares.

### Tasks Afetadas

| Repetição | Timeout | Status |
|-----------|---------|--------|
| 1 | 180s | Travou - marcado manualmente (2026-01-07 10:49) |
| 1 | 300s | Travou - marcado manualmente (2026-01-07 12:54) |
| 2 | 120s | Travou - marcado manualmente (2026-01-07 14:59) |
| 2 | 300s | Travou - marcado manualmente (2026-01-07 19:41) |
| 3 | 180s | Travou - marcado manualmente (2026-01-08 01:52) |

### Arquivos Gerados

- rep=1, timeout=180: `.logcat`: 16167 bytes, `.trace`: 277 bytes (com erro Python)
- rep=1, timeout=300: `.logcat`: 16167 bytes, `.trace`: 277 bytes (com erro Python)
- rep=2, timeout=120: `.logcat`: 16167 bytes, `.trace`: 356 bytes (com erro Python)
- rep=2, timeout=300: `.logcat`: 16167 bytes, `.trace`: 277 bytes (com erro Python)
- rep=3, timeout=180: `.logcat`: 16167 bytes, `.trace`: 277 bytes (com erro Python)

### Solução Aplicada

Task marcada manualmente como executada e container recriado (stop + rm + up).

### Análise

Mesmo padrão dos problemas #1 e #3. O ares tem um bug interno com certos APKs que causa o erro "cannot unpack non-iterable NoneType object". Este é o terceiro APK diferente a apresentar este problema específico.

---

## 6. APK de.igloffstein.maik.aRevelation_19.apk + qtesting

**Container**: 03 (batch 16)
**Data**: 2026-01-10

### Descrição

O APK `de.igloffstein.maik.aRevelation_19.apk` combinado com a ferramenta `qtesting` causou travamento do container.

### Sintomas

- Container congela durante execução do qtesting
- CPU cai para ~54%
- Logs param de ser gerados (0 linhas nos últimos 5 minutos)
- Emulador demorou muito para iniciar (3 min 56 seg)

### Tasks Afetadas

| Repetição | Timeout | Status |
|-----------|---------|--------|
| 1 | 60s | Travou - resume aplicado (2026-01-10 05:24) |

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Task será retomada automaticamente.

### Análise

Problema pontual com qtesting neste APK específico. Similar ao problema #2 (com.halftough.webcomreader_4.apk + qtesting). O qtesting parece ter problemas ocasionais com certos APKs que causam travamento do container.

---

## 7. Emulador não inicializa após troca de APK

**Container**: 04 (batch 24)
**Data**: 2026-01-11

### Descrição

O emulador travou ao tentar inicializar para processar o APK `kvj.taskw_3.apk` após ter concluído o APK `io.va.exposed_202.apk`.

### Sintomas

- Container fica em loop "Waiting for emulator to boot"
- CPU muito baixa (~0.08%)
- Memória muito baixa (~470MB de 16GB)
- Logs mostram tentativas contínuas de aguardar boot do emulador
- 29 tasks já executadas (io.va.exposed_202.apk completo)

### Tasks Afetadas

| APK | Repetição | Timeout | Tool | Status |
|-----|-----------|---------|------|--------|
| kvj.taskw_3.apk | 1 | 180s | droidmate | Travou - resume aplicado (2026-01-11 20:40) |

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Tasks serão retomadas automaticamente.

### Análise

Problema de inicialização do emulador Android entre APKs. O emulador não conseguiu reiniciar corretamente após processar um APK. Este tipo de problema é intermitente e relacionado ao ambiente de virtualização (KVM), não a um APK ou ferramenta específica.

---

## 8. Container travado após execução de task com ares

**Container**: 05 (batch 20)
**Data**: 2026-01-12

### Descrição

O container travou após completar a execução da task `godau.fynn.bandcampdirect_2.apk | rep=2 | timeout=300 | ares`. A task foi executada com sucesso (timeout normal), mas o container ficou travado ao tentar iniciar a próxima task.

### Sintomas

- Container congela após task completar
- CPU cai para ~22%
- Logs param de ser gerados (0 linhas nos últimos 10 minutos)
- Processos zombie detectados (adb, crashpad, sh defunct)
- 870/924 tasks já executadas (94.16%)

### Tasks Afetadas

| APK | Repetição | Timeout | Tool | Status |
|-----|-----------|---------|------|--------|
| godau.fynn.bandcampdirect_2.apk | 3 | 60s | droidbot_bfs_greedy | Próxima pendente - resume aplicado (2026-01-12 00:15) |

### Arquivos Gerados

A task `rep=2 | timeout=300 | ares` foi executada com sucesso:
- `.logcat`: 24059 bytes
- `.trace`: 1536 bytes

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Tasks serão retomadas automaticamente a partir de `rep=3`.

### Análise

O container travou após concluir uma task do ares, possivelmente durante a transição para a próxima task (kill emulator, start emulator). Este tipo de problema é intermitente e relacionado ao gerenciamento de processos do emulador, não a um APK ou ferramenta específica.

---

## 9. Containers travados durante execução do ares

**Containers**: 01 (batch 22) e 06 (batch 21)
**Data**: 2026-01-13

### Descrição

Containers 01 e 06 travaram durante execução de tasks com a ferramenta **ares**. Ambos os logcats mostram crash do aplicativo durante a execução.

### Sintomas

- Logs param de ser gerados (0 linhas nos últimos 5 minutos)
- CPU moderada (~17-23%)
- Memória normal (~3.7-4.4 GB)
- Logcat mostra "--------- beginning of crash"

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | .logcat | .trace |
|-----------|-------|-----|-----|---------|------|---------|--------|
| 01 | 22 | io.github.x0b.rcx_220.apk | 1 | 120s | ares | 16890 bytes | 145 bytes |
| 01 | 22 | io.github.x0b.rcx_220.apk | 1 | 180s | ares | 43363 bytes | 268 bytes (erro Python) |
| 01 | 22 | io.github.x0b.rcx_220.apk | 3 | 60s | ares | 43097 bytes | 145 bytes |
| 01 | 22 | io.github.x0b.rcx_220.apk | 3 | 180s | ares | 57864 bytes | 268 bytes |
| 06 | 21 | info.metadude.android.pyconza.schedule_84.apk | 2 | 300s | ares | 63080 bytes | 165 bytes |

### Progresso no Momento do Travamento

| Container | Batch | Tasks Completadas | Percentual |
|-----------|-------|-------------------|------------|
| 01 | 22 | 1200/1452 | 82.64% |
| 06 | 21 | 1530/1584 | 96.59% |

### Arquivos Gerados

Arquivos .logcat e .trace foram criados para as tasks. O .trace mostra apenas "Success" na instalação do APK, indicando que o ares iniciou mas não completou. O logcat mostra crash do aplicativo durante a execução do ares.

### Solução Aplicada

Containers recriados com resume config (stop + rm + up). Tasks serão retomadas automaticamente. As tasks com ares que travaram já possuem arquivos .logcat/.trace e serão consideradas como executadas.

### Análise

Mais um caso de travamento relacionado ao **ares**. Este é um padrão recorrente no experimento (problemas #1, #3, #4, #5, #8). O ares causa crashes ou travamentos em diversos APKs, provavelmente devido a:
- Incompatibilidade com certos APKs
- Problemas no framework Appium usado pelo ares
- Timeout não tratado corretamente pelo ares

---

## 10. Container 07 travado durante execução do ares

**Container**: 07 (batch 27)
**Data**: 2026-01-16

### Descrição

Container 07 travou durante execução de task com a ferramenta **ares**.

### Sintomas

- Logs param de ser gerados (0 linhas nos últimos 5 minutos)
- CPU baixa (~8.75%)
- Memória normal (~4.5GB)

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | Progresso |
|-----------|-------|-----|-----|---------|------|-----------|
| 07 | 27 | net.sf.andhsli.hotspotlogin_20.apk | 1 | 180s | ares | 1211/1584 (76.45%) |

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Tasks retomadas automaticamente.

### Análise

Mais um caso de travamento relacionado ao **ares**. Padrão recorrente no experimento.

---

## 11. Container 03 travado durante encerramento do emulador

**Container**: 03 (batch 32)
**Data**: 2026-01-17

### Descrição

Container 03 travou durante o encerramento do emulador após execução da task com droidbot_bfs_naive.

### Sintomas

- Logs param de ser gerados (0 linhas nos últimos 5 minutos)
- CPU muito baixa (~0.67%)
- Memória normal (~12.37GB)
- Último log: "Killing emulator ..."

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | Progresso |
|-----------|-------|-----|-----|---------|------|-----------|
| 03 | 32 | org.notabug.lifeuser.moviedb_211.apk | 3 | 60s | droidbot_bfs_naive | 620/1452 (42.7%) |

### Arquivos Gerados

Arquivos .logcat e .trace foram criados para a task:
- `.logcat`: presente
- `.trace`: presente

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Tasks retomadas automaticamente.

### Análise

O container travou durante o processo de encerramento do emulador ("Killing emulator..."). A task foi executada com sucesso (arquivos .logcat e .trace existem), mas o container ficou preso tentando matar o emulador. Este é um problema intermitente relacionado ao gerenciamento de processos do emulador.

---

## 12. Container 03 travado - emulador não consegue iniciar

**Container**: 03 (batch 32)
**Data**: 2026-01-17

### Descrição

Container 03 travou porque o emulador não conseguia iniciar. Ficou em loop "Waiting for emulator to boot" indefinidamente.

### Sintomas

- CPU muito baixa (~0.01%)
- Memória muito baixa (~139.9MiB de 16GB)
- Logs mostram loop contínuo de "Waiting for emulator to boot"
- 60 linhas nos últimos 5 minutos (todas iguais - waiting)

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | Progresso |
|-----------|-------|-----|-----|---------|------|-----------|
| 03 | 32 | org.notabug.lifeuser.moviedb_211.apk | 3 | 120s | droidmate | 633/1452 (43.6%) |

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Emulador iniciou normalmente após recreate.

### Análise

O emulador ficou preso tentando iniciar. Este é um problema intermitente relacionado ao ambiente de virtualização (KVM) e gerenciamento de processos do emulador. Recriar o container resolve o problema.

---

## 13. Container 06 travado durante execução do qtesting

**Container**: 06 (batch 28)
**Data**: 2026-01-18

### Descrição

Container 06 travou durante execução de task com qtesting. CPU moderada mas sem logs por mais de 5 minutos.

### Sintomas

- CPU moderada (~44.83%)
- Memória normal (~3.9GB)
- 0 linhas de log nos últimos 5 minutos

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | Progresso |
|-----------|-------|-----|-----|---------|------|-----------|
| 06 | 28 | ohi.andre.consolelauncher_205.apk | 3 | 300s | qtesting | 1451/1584 (91.6%) |

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Tasks retomadas automaticamente.

### Análise

Travamento durante execução do qtesting. Este é um problema pontual, similar ao problema #2 e #6. O qtesting ocasionalmente causa travamentos em certos APKs.

---

## 14. Container 06 travado durante instrumentação - APK removido do batch 36

**Container**: 06 (batch 36)
**Data**: 2026-01-18

### Descrição

Container 06 travou quatro vezes durante a fase de instrumentação/pré-processamento do batch 36:
1. Primeira vez: travou em "Extracting methods" após completar instrumentação 16/16
2. Segunda vez: travou em "Weaving monitors" para pt.ipleiria.mymusicqoe_12.apk (2/16)
3. Terceira vez: travou em "Weaving monitors" para wtf.nbd.obw_12.apk (3/16) - após reinício do computador
4. Quarta vez: travou em "Weaving monitors" para wtf.nbd.obw_12.apk (2/15) - após remoção do primeiro APK problemático

### Sintomas

- CPU muito baixa (~0.95-3%)
- 0 linhas de log nos últimos 5 minutos
- Parado em fases de pré-processamento (não chegou a iniciar experimento)
- Não havia timestamp de execução
- Erro Java: `ArrayIndexOutOfBoundsException: Index -1 out of bounds for length 0`

### APKs Removidos

1. `pt.ipleiria.mymusicqoe_12.apk` - causou erro (tool=d8) e travamento em "Weaving monitors"
2. `wtf.nbd.obw_12.apk` - causou travamento em "Weaving monitors" com ArrayIndexOutOfBoundsException

Ambos **removidos do batch 36** para permitir continuidade do experimento.
APKs.csv atualizado: ambos marcados como "REMOVED".

### Solução Final Aplicada

1. APKs pt.ipleiria.mymusicqoe_12.apk e wtf.nbd.obw_12.apk removidos do batch 36
2. BATCHES.csv atualizado (16→14 APKs, 12→10 instrumentáveis)
3. APKs.csv atualizado (ambos APKs marcados como REMOVED)
4. Diretórios limpos (instrumented, results)
5. Container recriado do zero

### Análise

Os APKs pt.ipleiria.mymusicqoe_12.apk e wtf.nbd.obw_12.apk têm problemas graves com o processo de instrumentação (AspectJ Weaving). Após múltiplas tentativas de reiniciar o batch, decidiu-se remover os APKs problemáticos para permitir a continuidade do experimento. O batch 36 agora tem 14 APKs em vez de 16 originalmente.

---

## 15. Container 04 travado múltiplas vezes - APK org.poul.bits.android_4.apk + ares

**Container**: 04 (batch 33)
**Data**: 2026-01-18 e 2026-01-19

### Descrição

Container 04 travou múltiplas vezes após o timeout do ares durante execução do APK `org.poul.bits.android_4.apk`.

### Sintomas

- 0 linhas de log nos últimos 5 minutos
- CPU moderada (~13-23%)
- Memória normal (~3.8GB)
- Último log: "The command has timeout after XX seconds" (ares)

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | Progresso | Data |
|-----------|-------|-----|-----|---------|------|-----------|------|
| 04 | 33 | org.poul.bits.android_4.apk | 1 | 60s | ares | 661/1320 (50.08%) | 2026-01-18 |
| 04 | 33 | org.poul.bits.android_4.apk | 1 | 180s | ares | 727/1320 (55.08%) | 2026-01-19 |
| 04 | 33 | org.poul.bits.android_4.apk | 2 | 180s | ares | - | 2026-01-19 |
| 04 | 33 | org.poul.bits.android_4.apk | 2 | 180s | ares | - | 2026-01-19 (4ª vez, marcado) |
| 04 | 33 | org.poul.bits.android_4.apk | 2 | 60s | ares | - | 2026-01-20 (5ª vez, marcado) |

### Solução Aplicada

1. Container recriado com resume config (stop + rm + up) em cada ocorrência
2. Tasks marcadas manualmente como executadas (arquivos .logcat e .trace existiam):
   - **rep=2, timeout=180, ares** (id=867): .logcat 822KB, .trace 851B
   - **rep=2, timeout=60, ares**: .logcat 149KB, .trace 218B
3. Todas as tasks ares com arquivos existentes foram marcadas para evitar travamentos futuros

### Arquivos Faltantes no Batch 33 (CORRIGIDO em 2026-01-26)

Devido ao erro de marcar todas as tasks ares como executadas (posteriormente corrigido), 2 tasks ficaram sem executar:
- `org.poul.bits.android_4.apk__3__180__ares.logcat`
- `org.poul.bits.android_4.apk__3__300__ares.logcat`

**Correção aplicada em 2026-01-26:**
1. Container 01 configurado para executar apenas as 2 tasks faltantes
2. APK copiado para batch especial (`fix-33`)
3. execution_memory.json criado com apenas as 2 tasks pendentes
4. Ambas as tasks executadas com sucesso
5. Arquivos .logcat e .trace copiados para `results/batch-33/20260116231309/org.poul.bits.android_4.apk/`
6. batch-33.zip atualizado com os novos arquivos

**Total de .logcat no batch 33: 1320 (esperado: 1320) ✓**

### Análise

O APK `org.poul.bits.android_4.apk` combinado com a ferramenta **ares** causa travamentos recorrentes. Este é o mesmo padrão observado em problemas anteriores (#1, #3, #4, #5, #8, #9, #10). O ares tem problemas com certos APKs que causam travamento após o timeout. Múltiplas tasks foram marcadas manualmente como executadas para permitir a continuidade do experimento. As 2 tasks que ficaram faltando foram re-executadas após o término do experimento.

---

## 16. Container 01 travado - emulador não inicializa

**Container**: 01 (batch 37)
**Data**: 2026-01-21

### Descrição

Container 01 travou em loop "Waiting for emulator to boot" ao tentar iniciar emulador para processar task.

### Sintomas

- Loop contínuo "Waiting for emulator to boot"
- CPU: ~14.52%
- Memória: ~4.2GB
- 60 linhas nos últimos 5 minutos (todas iguais - waiting)

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | Progresso |
|-----------|-------|-----|-----|---------|------|-----------|
| 01 | 37 | tk.giesecke.painlessmesh_14.apk | 3 | 120s | fastbot | 898/1584 (56.69%) |

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Emulador iniciou normalmente após recreate.

### Análise

Problema de inicialização do emulador Android. Similar aos problemas #7 e #12. O emulador fica preso tentando iniciar. Recriar o container resolve o problema.

---

## 17. Container 06 travado durante execução do qtesting

**Container**: 06 (batch 36)
**Data**: 2026-01-22

### Descrição

Container 06 travou durante execução de task com qtesting.

### Sintomas

- 0 linhas de log nos últimos 5 minutos
- CPU: ~28%
- Memória: ~5.2GB
- Emulador demorou 4 min 39 seg para iniciar

### Tasks Afetadas

| Container | Batch | APK | Rep | Timeout | Tool | Progresso |
|-----------|-------|-----|-----|---------|------|-----------|
| 06 | 36 | ru.yanus171.feedexfork_300.apk | - | - | qtesting | 1341/1452 (92.36%) |

### Solução Aplicada

Container recriado com resume config (stop + rm + up). Tasks retomadas automaticamente.

### Análise

Travamento durante execução do qtesting. Similar aos problemas #2, #6, e #13. O qtesting ocasionalmente causa travamentos em certos APKs.

---

## Template para Novos Problemas

```markdown
## N. [Breve descrição]

**Container**: XX (batch YY)
**Data**: YYYY-MM-DD

### Descrição
[Descrição detalhada do problema]

### Sintomas
- [Sintoma 1]
- [Sintoma 2]

### Tasks Afetadas
[Lista de tasks]

### Solução Aplicada
[O que foi feito para resolver]

### Arquivos Gerados
[Status dos arquivos de resultado]

### Análise
[Análise da causa raiz]
```
