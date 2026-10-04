"""
O objetivo deste script é extrair, discretizar e comprimir o trajeto espacial
e temporal de veiculos em uma simulação sumo para alimentar outros algoritmos de
processamento.
"""
import os
import sys
import polars
from dataclasses import dataclass, field
from typing import Tuple, List, Dict

if "SUMO_HOME" in os.environ:
    sys.path.append(os.path.join(os.environ["SUMO_HOME"], "tools"))
else:
    sys.exit("Please declare the environment variable 'SUMO_HOME'")

import traci


class DataframeToCsv:
    _data_chunks: List[Dict] = []

    @classmethod
    def append(cls, vehicle_id: int, start_time: float, gx: int, gy: int, count_r: int) -> None:
        """Adiciona um bloco comprimido (RLE) à lista em memória."""
        if count_r <= 0:
            return
        cls._data_chunks.append({
            "carro_id": vehicle_id,
            "tempo": start_time,
            "x": gx,
            "y": gy,
            "r": count_r
        })

    @classmethod
    def to_csv(cls) -> None:
        """Gera o DataFrame e salva o CSV uma única vez ao final."""
        if not cls._data_chunks:
            print("Nenhum dado para salvar.")
            return

        df = polars.DataFrame(cls._data_chunks)
        # Salva utilizando ';' como delimitador (formato esperado pelos programas em C)
        df.write_csv(Settings.OUTPUT_CSV, separator=";")
        print(f"[+] Arquivo salvo com sucesso em: {Settings.OUTPUT_CSV}")


@dataclass
class Settings:
    SUMO_CFG: str = "cologne6to8.sumocfg"
    OUTPUT_CSV: str = "TRACE-output.csv"
    GRID: int = 100
    SAMPLE_INTERVAL: int = 10
    SIMULATION_DURATION: int = 60 * 30


@dataclass
class RealWorldMapLimits:
    X_MIN: float
    X_MAX: float
    Y_MIN: float
    Y_MAX: float


def discretize(real_vehicle_position: Tuple[float, float], real_map: RealWorldMapLimits, grid: int) -> Tuple[int, int]:
    """
    Discretiza o mapa real para o GRID definido e retorna o indice da celula (gx, gy) em inteiro.
    """
    gx = int(max(0, min(((real_vehicle_position[0] - real_map.X_MIN) / (real_map.X_MAX - real_map.X_MIN)) * grid, grid - 1)))
    gy = int(max(0, min(((real_vehicle_position[1] - real_map.Y_MIN) / (real_map.Y_MAX - real_map.Y_MIN)) * grid, grid - 1)))

    return gx, gy


def main():
    # Conecta-se ao SUMO via TraCI em modo headless
    traci.start(["sumo", "-c", Settings.SUMO_CFG])

    # Obter a área do mapa real para discretização
    (x_min, y_min), (x_max, y_max) = traci.simulation.getNetBoundary()
    real_map = RealWorldMapLimits(x_min, x_max, y_min, y_max)

    # Mapeia carros (strings do SUMO) para IDs inteiros sequenciais (0, 1, 2...)
    id_map: Dict[str, int] = {}
    next_id = 0

    # Estado de cada veículo: veic_int -> ((gx, gy), tempo_inicio_bloco, contador_r)
    vehicle_state: Dict[int, Tuple[Tuple[int, int], float, int]] = {}

    vehicles = 0

    step = 0
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        step += 1

        if step % Settings.SAMPLE_INTERVAL == 0:
            current_time = traci.simulation.getTime()

            # 1. Processa veículos ativos na simulação
            for vehicle_id in traci.vehicle.getIDList():

                if vehicle_id not in id_map:
                    id_map[vehicle_id] = next_id
                    next_id += 1
                    vehicles += 1

                veic_int = id_map[vehicle_id]
                x, y = traci.vehicle.getPosition(vehicle_id)
                gx, gy = discretize((x, y), real_map, Settings.GRID)

                if veic_int not in vehicle_state:
                    # Primeiro bloco do veículo
                    vehicle_state[veic_int] = ((gx, gy), current_time, 1)
                else:
                    (prev_gx, prev_gy), t_start, r_count = vehicle_state[veic_int]

                    if prev_gx == gx and prev_gy == gy:
                        # Continua na mesma célula: incrementa r mantendo o tempo de início
                        vehicle_state[veic_int] = ((prev_gx, prev_gy), t_start, r_count + 1)
                    else:
                        # Mudou de célula: fecha o bloco anterior e abre um novo
                        DataframeToCsv.append(veic_int, t_start, prev_gx, prev_gy, r_count)
                        vehicle_state[veic_int] = ((gx, gy), current_time, 1)

            # 2. Processa veículos que chegaram ao destino (saíram do mapa)
            for arrived_id in traci.simulation.getArrivedIDList():
                if arrived_id in id_map:
                    arrived_int = id_map[arrived_id]
                    if arrived_int in vehicle_state:
                        (prev_gx, prev_gy), t_start, r_count = vehicle_state.pop(arrived_int)
                        DataframeToCsv.append(arrived_int, t_start, prev_gx, prev_gy, r_count)

    # 3. Flush final: descarrega os blocos de quem ainda estava trafegando quando o SUMO acabou
    for veic_int, ((prev_gx, prev_gy), t_start, r_count) in vehicle_state.items():
        DataframeToCsv.append(veic_int, t_start, prev_gx, prev_gy, r_count)

    print("[+] Encerrando executável do SUMO...")
    traci.close()
    DataframeToCsv.to_csv()
    print(f"[+] CSV salvo: {Settings.OUTPUT_CSV}")
    print(f"[+] Total de veiculos: {vehicles}")


if __name__ == '__main__':
    main()
