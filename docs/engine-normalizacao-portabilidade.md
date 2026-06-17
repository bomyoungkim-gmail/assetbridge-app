# ESPECIFICAÇÃO TÉCNICA DO PROJETO: ENGINE DE NORMALIZAÇÃO E PORTABILIDADE PATRIMONIAL ESPECIALIZADA (MVP)

## 1. OBJETIVO DO DOCUMENTO

Este documento especifica a arquitetura, a Tech Stack e os padrões de projeto para a construção de um MVP (Minimum Viable Product) de uma Plataforma de Normalização de Ativos Privados de Renda Fixa. O sistema deve processar injeções de dados de 300 carteiras simuladas vindas de múltiplos custodiantes com layouts de texto caóticos, higienizar os dados sem dependência exclusiva de chaves fortes regulatórias (como ISIN/CUSIP) e emitir um Identificador Universal de Portabilidade (IUP) único.

Para evitar falhas de falso positivo (como misturar ativos de mesmo emissor com vencimentos próximos), o sistema adota o padrão de projeto **Factory combinado com Strategy**, aplicando regras de isolamento e análise comportamental de caixa **especializadas por classe de ativo**.

---

## 2. REQUISITOS DE HARDWARE E AMBIENTE LOCAL

O código deve ser otimizado para rodar localmente no seguinte setup, priorizando baixo consumo de memória RAM e uso eficiente de paralelismo assíncrono:

- **Dispositivo:** Galaxy Book4 Ultra (Intel Core Ultra + NVIDIA RTX GPU dedicada com 6GB VRAM)
- **Engine de LLM Local:** Ollama rodando o modelo `llama3.1:8b-instruct-q4_K_M` ou `phi3.5` (via CUDA na GPU dedicada).
- **Paradigma de Código:** Python 3.11+ assíncrono (`asyncio`), Orientado a Objetos (Polimorfismo/Interfaces) e fortemente tipado com Pydantic.

---

## 3. TECH STACK (A PILHA TECNOLÓGICA DO MVP)

O assistente deve escrever o projeto utilizando estritamente as bibliotecas abaixo. É proibido o uso de Apache Spark, Pandas ou bancos de dados pesados externos.

- **Orquestrador de Fluxos e Estados:** `LangGraph` (para gerenciar nós, arestas condicionais, resiliência de falhas e checkpoints).
- **Ingestão e Processamento de Tabelas:** `DuckDB` (para queries analíticas diretas em arquivos locais) e `Polars` (para manipulação e parsing de DataFrames em memória de forma multi-threaded).
- **Interface com LLM Local:** `langchain_ollama` (classe `ChatOllama`).
- **Banco de Dados Operacional e Checkpointer:** `SQLite` (embutido nativamente no LangGraph via `MemorySaver` ou `SqliteSaver`).
- **Engine Vetorial / Busca Local:** `Faiss` ou `ChromaDB` (armazenamento e busca in-memory salvando em arquivo local).

---

## 4. ESCOPO DA ARQUITETURA DE DADOS ESPECIALIZADA

A arquitetura do MVP deve implementar **duas camadas integradas**, controladas dinamicamente por uma Fábrica de Estratégias (`AssetStrategyFactory`). O fluxo do grafo nunca deve tentar adivinhar dados usando similaridade textual na string inteira.

```
                    ┌─────────────────────────┐
                    │  Injeção de Texto Bruto │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  AssetStrategyFactory   │
                    └────────────┬────────────┘
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   CdbStrategy    │    │  CraCriStrategy  │    │    LfStrategy    │
└──────────────────┘    └──────────────────┘    └──────────────────┘

```

### CAMADA 1: Pipeline de Isolamento Atômico Especializado

A primeira camada limpa os ruídos textuais e extrai os metadados do ativo. Em vez de uma lógica genérica, os extratores devem aplicar expressões regulares (Regex) customizadas por classe:

#### 1. Estratégia para CDB / RDP (Crédito Bancário)

- **Foco do Regex:** Capturar o CNPJ ou o nome do Banco Emissor comercial. Limpar stop-words como `BANCO`, `S/A`, `INVESTIMENTOS`.
- **Padrão de Taxa:** Isolar percentuais fixos do CDI (ex: `103%`, `100%`) ou taxas pré-fixadas (ex: `11.5% a.a.`).

#### 2. Estratégia para CRA / CRI (Securitização de Agronegócio/Imobiliário)

- **Foco do Regex:** Capturar obrigatoriamente a **Série** e a **Emissão** do papel usando padrões numéricos específicos (ex: `\b\d+[S|s]\b`, `\b\d+ª?\s*[S|s]é[r|i]e\b`, `\b\d+ª\s*[E|e]miss[a|ã]o\b`).
- **Mapeamento de Emissor:** Diferenciar a Securitizadora (emissora legal, ex: Opea, Virgo) do devedor/lastro real do projeto (ex: Iguatemi, JBS) contido no texto.

#### 3. Estratégia para LF / LFN (Letra Financeira)

- **Foco do Regex:** Buscar por indicadores de **Subordinação** (`SUB`, `SUBORDINADA`, `SENIOR`, `SEN`) e **Perpetuidade**. A detecção da palavra `SUB` deve ligar uma flag booleana estruturada no Estado, alterando a identidade do papel.

#### Geração da Identidade Sintética Provisória:

Após a extração especializada, o sistema compila a assinatura gerando um hash `SHA-256` exclusivo dos metadados extraídos. Se mudar um caractere de série (CRI) ou a flag de subordinação (LF), o hash muda completamente, eliminando falsos positivos textuais.

---

### CAMADA 2: O Motor Relacional e Caixa Comportamental Especializado

Se a Chave Sintética for inédita no sistema, o Grafo do LangGraph deve desviar para a Camada de Inteligência Relacional para decidir se cria um novo ativo ou o acopla a um existente usando lógicas de negócio e séries temporais customizadas:

| Classe de Ativo | Motor de Caixa Espelhado (Série Temporal)                                                                                                                                                                                                       | Lógica do Data Graph de Aliases (Relações)                                                                                                           |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| **CDB / RDP**   | **Rendimento Linear (Bullet):** O preço unitário (PU) cresce linearmente acompanhando o CDI. Sem cupons intermediários ou amortização. A curva é validada via regressão matemática simples.                                                     | O Grafo de Aliases vincula o nome fantasia extraído diretamente à base de CNPJs de bancos comerciais cadastrados no Banco Central.                   |
| **CRA / CRI**   | **Fluxo Periódico com Amortização:** O motor de caixa deve suportar **amortizações constantes** do principal e pagamento de cupons mensais/trimestrais, frequentemente atrelados ao IPCA. A similaridade usa distorção dinâmica de tempo (DTW). | O Grafo mapeia uma relação triangular: `[Texto Custodiante] ──► [Securitizadora] ──► [Lastro Real/Devedor]`.                                         |
| **LF / LFN**    | **Cupons Semestrais Sem Amortização:** O motor valida o comportamento de pagamento de juros estritos a cada 6 meses, mantendo o principal intacto até a data de liquidação (vencimento maior que 24 meses).                                     | O Grafo valida a alçada do banco emissor. Se o ativo for marcado como `Subordinado`, ele é impedido de se fundir com uma LF sênior do mesmo emissor. |

#### Geração do Identificador Universal de Portabilidade (IUP) Semântico:

Caso o ativo seja validado como novo por todas as etapas, o sistema gera o IUP final estruturado de forma auto-explicativa e especializada:

- _CDB:_ `IUP-CDB-{CNPJ_EMISSOR}-{VENCIMENTO_YYYYMMDD}-{TAXA}`
- _CRI/CRA:_ `IUP-CRI-{CNPJ_SECURITIZADORA}-SERIE{SERIE}-{VENCIMENTO_YYYYMMDD}`
- _LF:_ `IUP-LF-{CNPJ_EMISSOR}-SUB-{VENCIMENTO_YYYYMMDD}`

---

## 5. DESIGN DO GRAFO E ARQUITETURA NO PYTHON

O assistente deve estruturar o código do MVP implementando estritamente a arquitetura de classes baseada em estratégias polimórficas dentro dos nós do LangGraph.

### A. Estrutura do Estado (`State`) e Modelos Pydantic

```python
from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel, Field

class RawInputPayload(BaseModel):
    descricao_bruta: str
    custodiante: str
    valores_caixa_historico: List[float] = Field(default_factory=list) # Série temporal de PUs

class AtivoNormalizado(BaseModel):
    iup: str
    tipo_ativo: str
    emissor_identificado: str
    data_vencimento: str
    taxa_indexador: str
    serie_emissao: Optional[str] = None
    is_subordinado: bool = False
    chave_sintetica_provisoria: str

class ReconciliacaoState(TypedDict):
    id_carteira: str
    custodiante: str
    dados_brutos: List[Dict[str, Any]]
    dados_normalizados: List[Dict[str, Any]]
    divergencias: List[Dict[str, Any]]
    status_fluxo: str  # "Processando", "Pausado_Mesa", "Sucesso"

```

### B. O Padrão Strategy para Especialização dos Ativos

```python
from abc import ABC, abstractmethod
import re
import hashlib

class AssetStrategy(ABC):
    @abstractmethod
    def extrair_metadados_camada_1(self, texto: str) -> dict:
        """Executa a limpeza e extração atômica via Regex especializado."""
        pass

    @abstractmethod
    def analisar_comportamento_caixa_camada_2(self, serie_historica: list, serie_banco: list) -> float:
        """Calcula a correlação matemática baseada na dinâmica do fluxo de caixa do ativo."""
        pass

# IMPLEMENTAÇÃO ESPECIALIZADA PARA CRI / CRA
class CraCriStrategy(AssetStrategy):
    def extrair_metadados_camada_1(self, texto: str) -> dict:
        texto_up = texto.upper()
        # Regex cirúrgico para capturar Séries (ex: 13S, 142ª SERIE)
        serie_match = re.search(r'\b\d+\s*[S|s]\b|\b\d+ª?\s*[S|s]é[r|i]e\b', texto_up)
        serie = serie_match.group(0) if serie_match else "SÉRIE_NÃO_INFORMADA"

        # Isolar Securitizadora e Lastro (Simulação de regras)
        emissor = "SECURITIZADORA_GENERICA"
        if "OPEA" in texto_up: emissor = "OPEA"
        elif "VIRGO" in texto_up: emissor = "VIRGO"

        return {"tipo": "CRI", "emissor": emissor, "serie_emissao": serie, "is_subordinado": False}

    def analisar_comportamento_caixa_camada_2(self, serie_historica: list, serie_banco: list) -> float:
        # Algoritmo que entende decaimento por amortização e indexação de inflação
        # Retorna o coeficiente de proximidade/correlação de 0 a 1
        return 0.98

# IMPLEMENTAÇÃO ESPECIALIZADA PARA LETRA FINANCEIRA (LF)
class LfStrategy(AssetStrategy):
    def extrair_metadados_camada_1(self, texto: str) -> dict:
        texto_up = texto.upper()
        # Identifica risco de subordinação (Garante que sênior e subordinada nunca se fundam)
        is_sub = True if re.search(r'\bSUB\b|\bSUBORDINADA\b', texto_up) else False

        emissor = "BANCO_EMISSOR_LF"
        if "ITAU" in texto_up: emissor = "ITAU"

        return {"tipo": "LF", "emissor": emissor, "serie_emissao": None, "is_subordinado": is_sub}

    def analisar_comportamento_caixa_camada_2(self, serie_historica: list, serie_banco: list) -> float:
        # Algoritmo de validação de repasses semestrais de cupons rígidos
        return 0.95

# A FÁBRICA DE ESTRATÉGIAS
class AssetStrategyFactory:
    @staticmethod
    def obter_estrategia(texto_bruto: str) -> AssetStrategy:
        texto_up = texto_bruto.upper()
        if "CRI" in texto_up or "CRA" in texto_up:
            return CraCriStrategy()
        elif "LF" in texto_up:
            return LfStrategy()
        # Fallback padrão para CDBs e outros papéis lineares
        return CdbDefaultStrategy()

```

### C. Implementação dos Nós no LangGraph

O assistente deve construir os nós do `StateGraph` invocando a fábrica dinamicamente para cada linha da carteira processada:

```python
def node_isolamento_atomico_especializado(state: ReconciliacaoState):
    dados_normalizados = []

    for item in state["dados_brutos"]:
        texto_bruto = item["descricao_bruta"]

        # Invoca a Fábrica Especializada com base na pista de texto
        estrategia = AssetStrategyFactory.obter_estrategia(texto_bruto)

        # Executa as regras de extração cirúrgicas daquela classe de ativo
        metadados = estrategia.extrair_metadados_camada_1(texto_bruto)

        # Extrações comuns (Datas de vencimento padronizadas em ISO)
        data_vencimento = extrair_data_iso_comum(texto_bruto)
        taxa = extrair_taxa_comum(texto_bruto)

        # Compila a string de assinatura imutável para gerar o Hash Sintético Provisório
        assinatura = f"{metadados['tipo']}_{metadados['emissor']}_{data_vencimento}_{taxa}_{metadados['serie_emissao']}_{metadados['is_subordinado']}"
        hash_sintetico = hashlib.sha256(assinatura.encode('utf-8')).hexdigest()[:12]

        dados_normalizados.append({
            "chave_sintetica_provisoria": f"sint_{hash_sintetico}",
            **metadados,
            "data_vencimento": data_vencimento,
            "taxa_indexador": taxa
        })

    return {"dados_normalizados": dados_normalizados}

```

### D. Regras de Concorrência e Human-in-the-loop (Four-Eyes Principle)

- **Isolamento Total:** Processar as 300 carteiras concorrentemente usando chaves exclusivas de `thread_id` gravadas no `SqliteSaver`.
- **Interrupts por Incerteza Comportamental:** O grafo deve pausar antes da gravação do IUP definitivo (`interrupt_before=["node_gravar_iup_banco"]`) caso o algoritmo de caixa espelhado da estratégia retorne uma correlação de ambiguidade na zona cinzenta (ex: entre $0.75$ e $0.90$).
- **Mapeamento Mutável:** O de-para manual feito pelo backoffice deve ser guardado em tabela relacional com histórico de logs, permitindo reversão imediata de associações sem corromper a base histórica do motor de Big Data.

---

Aqui está o trecho final detalhado da seção **6. Diretrizes de Saída do Código**, estruturado especificamente para instruir o assistente a fechar o script com um simulador funcional de estresse, aproveitando ao máximo o paralelismo do seu hardware:

---

## 6. DIRETRIZES DE SAÍDA DO CÓDIGO (CONTINUAÇÃO E EXECUÇÃO)

O assistente deve fornecer o código Python completo do MVP respeitando a seguinte estrutura lógica de blocos e scripts de fechamento:

### E. Script Simulador de Carga e Estresse Concorrente

Para testar a resiliência física do hardware (Intel Core Ultra + GPU via Ollama), o assistente deve incluir um script executável ao final do arquivo contendo as seguintes rotinas:

1. **Massa de Dados de Teste:**
   Criar um gerador de dados que simule as strings caóticas para as 300 carteiras, injetando propositalmente cenários de falha para testar os motores especializados:
   - **Cenário CDB:** Mesmos emissores textuais com taxas ligeiramente diferentes para validar que geram chaves sintéticas distintas.
   - **Cenário CRI:** Strings variando o formato da série ("12S" vs "SERIE 12") para testar a robustez do Regex polimórfico.
   - **Cenário LF:** Duas LFs do mesmo banco vencendo no mesmo dia, sendo uma `SENIOR` e outra `SUBORDINADA` para validar o isolamento por flag de risco.
   - **Cenário Ambiguidade (Mesa):** Ativos com nomes completamente irreconhecíveis para forçar o acionamento do `interrupt_before` e simular o congelamento da Thread no SQLite.

2. **Orquestração Assíncrona (`asyncio.gather`):**
   O loop de execução deve disparar o processamento das carteiras de forma assíncrona concorrente, simulando um ambiente de produção multiusuário em tempo real. Cada carteira deve ser tratada como um evento isolado passando seu respectivo `thread_id`:

```python
import asyncio

async def rodar_esteira_mvp():
    # Inicializa o checkpointer SQLite embutido para auditoria local
    memory_saver = SqliteSaver.from_conn_string(":memory:")
    app = builder.compile(checkpointer=memory_saver, interrupt_before=["node_gravar_iup_banco"])

    # Gera a carga de 300 carteiras mistas
    carteiras_para_processar = gerar_massa_de_teste_300_carteiras()

    # Dispara todas as tarefas em paralelo aproveitando os cores de performance do Core Ultra
    tarefas = []
    for i, dados_carteira in enumerate(carteiras_para_processar):
        config = {"configurable": {"thread_id": f"thread_carteira_00{i}"}}
        # Execução assíncrona do grafo do LangGraph
        tarefas.append(app.ainvoke(dados_carteira, config))

    # Aguarda a finalização do lote concorrente
    resultados = await asyncio.gather(*tarefas, return_exceptions=True)
    print(f"Processamento concluído para {len(resultados)} carteiras.")

if __name__ == "__main__":
    asyncio.run(rodar_esteira_mvp())

```

3. **Métricas de Performance Operacional:**
   O script deve exibir no console um relatório simples de encerramento contendo:

- Tempo total gasto para processar o lote de 300 carteiras.
- Quantidade de ativos normalizados com sucesso imediato via Camada 1.
- Quantidade de ativos que exigiram o fallback do Motor de Caixa da Camada 2.
- Quantidade de threads congeladas com sucesso no SQLite aguardando intervenção humana (_Human-in-the-loop_).
