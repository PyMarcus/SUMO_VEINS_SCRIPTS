# Guia Completo de Operação e Simulação: SUMO & Veins (OMNeT++)

Este guia fornece uma referência detalhada para a execução, configuração e manipulação de simulações de mobilidade viária com **SUMO** (*Simulation of Urban MObility*) e simulações de redes veiculares (VANETs/C-V2X) com **Veins** e **OMNeT++**.

## Sumário

1. [Fluxo e Operação do SUMO](#1-fluxo-e-operação-do-sumo)

   * [Baixar e Converter Mapas Reais (OpenStreetMap)](#baixar-e-converter-mapas-reais-openstreetmap)

   * [Significado dos Arquivos Principais do SUMO](#significado-dos-arquivos-principais-do-sumo)

   * [Modos de Execução do SUMO](#modos-de-execução-do-sumo)

2. [Fluxo e Operação do Veins & OMNeT++](#2-fluxo-e-operação-do-veins--omnet)

   * [Arquitetura de Execução](#arquitetura-de-execução)

   * [Comandos de Execução](#comandos-de-execução)

   * [Significado dos Arquivos do Veins](#significado-dos-arquivos-do-veins)

   * [Análise Detalhada do `RSUExampleScenario.ned`](#análise-detalhada-do-rsuexamplescenarioned)

## 1. Fluxo e Operação do SUMO

### Baixar e Converter Mapas Reais (OpenStreetMap)

Existem duas formas principais de obter um mapa real para o SUMO:

#### Método A: Assistente Gráfico (`osmWebWizard.py`)

O método mais rápido para baixar e gerar tráfego automático de uma área:

```
python3 $SUMO_HOME/tools/osmWebWizard.py

```

* O navegador abrirá automaticamente. Selecione a área desejada no mapa.

* Configure os parâmetros de tráfego (carros, pedestres, transporte público).

* Clique em **Generate Scenario**. O SUMO criará uma pasta local contendo a rede e os arquivos de rotas compilados.

#### Método B: Linha de Comando Manual (Maior Controle)

Para pipeline automatizado ou áreas customizadas:

1. **Baixar o arquivo `.osm` da região via cURL/Wget (OpenStreetMap API):**

   ```
   # Formato das coordenadas: bbox=min_lon,min_lat,max_lon,max_lat
   curl -o meu_mapa.osm "https://api.openstreetmap.org/api/0.6/map?bbox=13.37,52.51,13.38,52.52"
   
   ```

2. **Converter o `.osm` para a rede do SUMO (`.net.xml`):**

   ```
   netconvert --osm-files meu_mapa.osm -o meu_mapa.net.xml --geometry.remove --ramps.guess --junctions.join
   
   ```

3. **Gerar rotas aleatórias (`.rou.xml`) para testes:**

   ```
   python3 $SUMO_HOME/tools/randomTrips.py -n meu_mapa.net.xml -e 3600 -p 1.0 -o rotas.trips.xml
   duarouter --net-file meu_mapa.net.xml --route-files rotas.trips.xml -o meu_mapa.rou.xml
   
   ```

### Significado dos Arquivos Principais do SUMO

| 

| **Arquivo** | **Descrição** | 
| `.net.xml` | **Malha Viária Discreta.** Contém as vias (*edges*), faixas (*lanes*), nós/cruzamentos (*junctions*), regras de prioridade e semáforos. | 
| `.rou.xml` | **Rotas e Demandas.** Define os tipos de veículos (`vType`), origens, destinos, horários de saída e o conjunto de vias percorridas. | 
| `.poly.xml` | **Polígonos e Edificações.** Contém informações de geometria 2D/3D dos prédios, rios e parques (essencial para sombreamento/bloqueio de sinal de rádio no Veins). | 
| `.sumocfg` | **Arquivo de Configuração Master.** Une a rede, rotas e polígonos, definindo o tempo de início/fim ($t_{start}$, $t_{end}$) e a resolução do passo de simulação (`step-length`). | 

### Modos de Execução do SUMO

#### 1. Modo Gráfico (`sumo-gui`)

Ideal para validação visual, verificação de engarrafamentos e depuração inicial:

```
sumo-gui -c meu_mapa.sumocfg

```

#### 2. Modo Headless/CLI (`sumo`)

Ideal para benchmarking, simulações em massa e execução via script Python/TraCI ou C++:

```
sumo -c meu_mapa.sumocfg --no-step-log true --time-to-teleport -1

```

#### 3. Via TraCI em Python (Server-Client)

```
import traci

traci.start(["sumo", "-c", "meu_mapa.sumocfg"])
while traci.simulation.getMinExpectedNumber() > 0:
    traci.simulationStep()
traci.close()

```

## 2. Fluxo e Operação do Veins & OMNeT++

### Arquitetura de Execução

O Veins conecta o simulador de eventos discretos de rede (**OMNeT++**) ao simulador de tráfego (**SUMO**) usando o protocolo **TraCI** sobre um socket TCP/IP.

```
+------------------+                    +-------------------+
|     OMNeT++      | <--- TraCI Socket  |  veins_launchd    |
| (Simulador Rede) |     (Porta 9999)   |   (Daemon Python) |
+------------------+                    +---------+---------+
                                                  |
                                             Lança & Controla
                                                  v
                                        +-------------------+
                                        |   SUMO / SUMO-GUI |
                                        | (Simulador Tráfego|
                                        +-------------------+

```

### Comandos de Execução

Para rodar uma simulação do Veins corretamente, você precisa de **dois terminais**.

#### Terminal 1: Orquestrador (`veins_launchd`)

O daemon monitora solicitações do OMNeT++ e inicia uma instância do SUMO sob demanda:

```
cd ~/veins/examples/veins
./../../bin/veins_launchd -vv -c sumo-gui

```

> **Nota:** Substitua `-c sumo-gui` por `-c sumo` se quiser rodar a mobilidade em segundo plano sem interface gráfica para maior performance.

#### Terminal 2: Execução da Simulação do OMNeT++

##### Opção A: Usando o wrapper nativo do exemplo (`./veins_example`)

* **Interface Gráfica (`Qtenv` - Recomendado para depuração visual de rede):**

  ```
  ./veins_example -u Qtenv -c Default -f omnetpp.ini
  
  ```

* **Modo Linha de Comando (`Cmdenv` - Alta performance e execução remota):**

  ```
  ./veins_example -u Cmdenv -c Default -f omnetpp.ini
  
  ```

##### Opção B: Usando o comando nativo do OMNeT++ (`opp_run`)

Utilizado para automação, servidores sem GUI e varredura de parâmetros:

```
opp_run -m -l ../../src/libveins.so -u Qtenv -c Default omnetpp.ini

```

##### Significado dos Parâmetros do `opp_run`:

* `-m` (*merge*): Carrega automaticamente todos os arquivos NED e definições de topologia das pastas filhas.

* `-l <path>` (*library*): Faz a ligação dinâmica com a biblioteca compilada em C++ do Veins (`libveins.so` no Linux ou `.dll` no Windows).

* `-u <interface>` (*user interface*): Define a interface do usuário: `Qtenv` (gráfica) ou `Cmdenv` (terminal/texto).

* `-c <config>` (*configuration*): Especifica a seção dentro do `omnetpp.ini` que deve ser executada (ex: `Default`, `General`, `RSUScenario`).

* `-f <file>` (*file*): Arquivo de inicialização de parâmetros.

### Significado dos Arquivos do Veins

| **Arquivo** | **Descrição** | 
| `omnetpp.ini` | **Configuração Global da Simulação.** Define frequência do rádio ($5.9\text{ GHz}$), potência de transmissão ($mW/dBm$), modelo de sensibilidade, caminho para o `veins_launchd` e tempo total de simulação. | 
| `.ned` (*Network Description*) | **Definição da Topologia.** Linguagem declarativa do OMNeT++ para especificar módulos, conexões, canais e estruturas hierárquicas da rede. | 
| `*.cc` / `*.h` | **Lógica C++.** Define o comportamento dos módulos, protocolos de controle de acesso ao meio (MAC), camada física (PHY) e aplicações veiculares (`VeinsApp`). | 
| `.vec` / `.sca` | **Resultados de Saída.** Arquivos de vetores temporais (`.vec`) e estatísticas escalares (`.sca`) gerados ao final para calcular métricas como PDR (*Packet Delivery Ratio*) e latência. | 

### Análise Detalhada do `RSUExampleScenario.ned`

O arquivo `RSUExampleScenario.ned` define a estrutura física e lógica de uma simulação contendo veículos e Unidades de Beira de Estrada (**RSUs**).

#### Código Típico do `RSUExampleScenario.ned`:

```
package veins.examples.veins;

import veins.nodes.RSU;
import veins.nodes.Scenario;

network RSUExampleScenario extends Scenario
{
    submodules:
        rsu[1]: RSU {
            @display("p=150,140;i=veins/single/antenna");
        }
}

```

#### Desconstrução Bloco a Bloco:

1. **`package veins.examples.veins;`**

   * Define o *namespace* do OMNeT++ onde este cenário está cadastrado, permitindo a importação dos módulos em outros arquivos.

2. **`import veins.nodes.RSU;` e `import veins.nodes.Scenario;`**

   * Importa a definição básica de uma **RSU** (um nó fixo equipado com pilha de protocolos de rádio 802.11p/C-V2X) e do **Scenario** base do Veins (que inclui o gerenciador do canal de rádio e o conector TraCI).

3. **`network RSUExampleScenario extends Scenario`**

   * Declara a rede principal chamada `RSUExampleScenario`. Ao estender (`extends`) `Scenario`, ela herda automaticamente:

     * **`manager` (`TraCIScenarioManager`):** Responsável pela ponte com o SUMO.

     * **`obstacles` (`ObstacleControl`):** Responsável por calcular a atenuação de sinal por prédios.

     * **`annotations` (`AnnotationManager`):** Responsável pelos desenhos gráficos de links de rádio e animações.

4. **`submodules:`**

   * Bloco onde os elementos estáticos da rede são instanciados.

5. **`rsu[1]: RSU`**

   * Instancia um **array de submódulos** do tipo `RSU`. O número `[1]` define a quantidade de RSUs alocadas estaticamente na rede (pode ser alterado para `rsu[K]` ou parametrizado via `omnetpp.ini`).

6. **`@display("p=150,140;i=veins/single/antenna");`**

   * Metadados visuais para a interface gráfica (`Qtenv`):

     * `p=150,140`: Posição $(X, Y)$ da RSU no canvas de simulação do OMNeT++.

     * `i=veins/single/antenna`: Ícone gráfico exibido na tela.

````

---
