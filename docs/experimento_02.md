# Experimento 02: Execução Longa

## Objetivo

Avaliar o comportamento das ferramentas de geração de testes em execuções prolongadas (3 horas), identificando se o tempo adicional de exploração resulta em maior cobertura de código e detecção de violações.

## Configuração

| Parâmetro | Valor |
|-----------|-------|
| APKs | 10 (selecionados) |
| Timeout | 10800 segundos (3 horas) |
| Repetições | 1 |
| Ferramentas | 5 |

## Ferramentas Selecionadas

A seleção das ferramentas foi baseada nos resultados do Experimento 01, considerando dois critérios principais:
- **Cobertura de código** (métodos alcançados)
- **Detecção de erros** (violações de specs identificadas)

### Ranking do Experimento 01 (Timeout 300s)

| Ferramenta | Cobertura | Posição Cov | Violações | Posição Viol |
|------------|-----------|-------------|-----------|--------------|
| HUMANOID | 26.77% | 1º | 221 | 1º |
| FASTBOT | 26.60% | 2º | 213 | 2º |
| APE | 25.27% | 3º | 198 | 5º |
| DROIDBOT_BFS_GREEDY | 24.45% | 4º | 205 | 3º |
| DROIDBOT_DFS_GREEDY | 24.45% | 5º | 202 | 4º |

### Ferramentas Escolhidas

| Ferramenta | Ranking Cov | Ranking Erros | Justificativa |
|------------|-------------|---------------|---------------|
| **HUMANOID** | 1º | 1º | Melhor desempenho em ambos os critérios (26.77% cov, 221 viol) |
| **FASTBOT** | 2º | 2º | Segundo melhor em ambos os critérios (26.60% cov, 213 viol) |
| **APE** | 3º | 5º | Top 3 em cobertura (25.27%), representa abordagem model-based |
| **DROIDBOT_BFS_GREEDY** | 4º | 3º | Bom equilíbrio (24.45% cov, 205 viol), estratégia BFS |
| **DROIDBOT_DFS_GREEDY** | 5º | 4º | Variante DFS (24.45% cov, 202 viol) para comparação |

### Critérios de Seleção

1. **Top 5 consolidado**: As 5 ferramentas selecionadas aparecem consistentemente nas primeiras posições em ambos os rankings.

2. **Diversidade de abordagens**:
   - HUMANOID: Aprendizado de máquina para geração de eventos
   - FASTBOT: Exploração rápida baseada em modelo
   - APE: Model-based testing com abstração de estado
   - DROIDBOT_BFS/DFS: Estratégias de busca em largura e profundidade

3. **Comparação BFS vs DFS**: Incluir ambas as variantes do DroidBot permite analisar qual estratégia de exploração é mais eficaz em execuções longas.

### Ferramentas Excluídas

| Ferramenta | Motivo |
|------------|--------|
| MONKEY | Geração puramente aleatória, desempenho inferior |
| ARES | Ficou abaixo do top 5 em ambos os critérios |
| DROIDMATE | Desempenho inferior nas métricas avaliadas |
| DROIDBOT (padrão) | Substituído pelas variantes BFS/DFS mais específicas |
| DROIDBOT_BFS_NAIVE | BFS_GREEDY mostrou resultados superiores |
| QTESTING | Não alcançou top 5 em nenhum critério |

## Execução

```bash
# Configuração do .env
RV_TOOLS=humanoid fastbot ape droidbot_bfs_greedy droidbot_dfs_greedy
RV_TIMEOUTS=10800
RV_REPETITIONS=1
```

## Questões de Pesquisa

1. **RQ1**: O tempo adicional de exploração (3h vs 5min) resulta em aumento proporcional de cobertura?
2. **RQ2**: As ferramentas mantêm a mesma ordem de ranking em execuções longas?
3. **RQ3**: Existe um ponto de saturação onde exploração adicional não gera novos resultados?

## APKs Selecionados

Os mesmos 10 APKs utilizados no Experimento 02 do estudo JCA original, permitindo comparação direta:

| Container | APK |
|-----------|-----|
| rv01 | com.blogspot.e_kanivets.moneytracker_38.apk |
| rv01 | com.gianlu.dnshero_40.apk |
| rv02 | com.github.axet.hourlyreminder_476.apk |
| rv02 | com.pindroid_69.apk |
| rv03 | com.rafapps.simplenotes_7.apk |
| rv03 | com.thibaudperso.sonycamera_24.apk |
| rv04 | li.klass.fhem_141.apk |
| rv04 | org.pulpdust.lesserpad_42.apk |
| rv05 | org.secuso.privacyfriendlydicer_8.apk |
| rv05 | org.secuso.privacyfriendlyludo_5.apk |

## Estrutura de Arquivos

```
exp02/
├── docker-compose-exp02.yml    # Orquestração dos 5 containers + humanoid
├── .env-exp02                  # Variáveis de ambiente
├── apks/                       # (vazio - APKs nos containers)
├── results/                    # Resultados consolidados
└── containers/
    ├── 01/
    │   ├── apks/               # 2 APKs
    │   ├── instrumented/       # APKs instrumentados
    │   ├── results/            # Resultados da execução
    │   └── specs/              # 27 Generic Specs
    ├── 02/ ... 05/             # Mesma estrutura
```

## Execução

```bash
# Navegar para o diretório do experimento
cd exp02

# Iniciar (quando aprovado)
docker compose -f docker-compose-exp02.yml --env-file .env-exp02 up -d

# Verificar status
docker ps --filter "name=rv-exp02"

# Logs de um container específico
docker logs rv-exp02-01 --tail 50 -f
```

## Tempo Estimado

- **Por container**: 2 APKs × 5 tools × 1 rep × 3h = 30 horas (sequencial)
- **Total**: ~30 horas (5 containers em paralelo)
