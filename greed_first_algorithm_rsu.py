import os
import pickle
import math
import xml.etree.ElementTree as ET

import matplotlib.pyplot as plt
import polars as pl
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.patches import Circle, Patch
from dataclasses import dataclass

# --- Configurações -----------------------------------------------------------
NET_FILE = "cologne.net.xml"
CSV_FILE = "TRACE-0-ordenado.csv"
TIME = 32331.0  # 21611 32331
TOL = 1e-6
DT = None  # Ajuste para o intervalo do seu RLE em segundos se necessário
SHOW = True
OUT_FILE = f"colonia_{int(TIME)}_rsu.png"

# Grade e Escala
NET_WIDTH_M, NET_HEIGHT_M = 32300.19, 34380.22
GRID_N = 100
CELL_W_M = NET_WIDTH_M / GRID_N
CELL_H_M = NET_HEIGHT_M / GRID_N

# --- Parâmetros de Alocação e Comunicação ------------------------------------
EXCLUSION_RADIUS_CELLS = 2  # Raio de exclusão no algoritmo (evita RSUs coladas)
RSU_COVERAGE_METERS = 300.0   # Alcance real da antena RSU em metros (C-V2X / DSRC)


@dataclass
class RSU:
    x: int
    y: int
    veh_count: int


def load_streets(net_file: str) -> list:
    """Carrega as ruas do .net.xml mantendo o cache pkl."""
    cache = net_file + ".streets.pkl"
    if os.path.exists(cache) and os.path.getmtime(cache) >= os.path.getmtime(net_file):
        with open(cache, "rb") as f:
            return pickle.load(f)

    print(f"Lendo ruas de {net_file}...")
    segments = []
    for _, elem in ET.iterparse(net_file, events=("end",)):
        if elem.tag == "lane":
            lane_id = elem.get("id", "")
            if not lane_id.startswith(":") and lane_id.endswith("_0"):
                shape = elem.get("shape")
                if shape:
                    pts = [tuple(map(float, p.split(",")[:2])) for p in shape.split()]
                    if len(pts) >= 2:
                        segments.append(pts)
        elem.clear()

    with open(cache, "wb") as f:
        pickle.dump(segments, f)
    return segments


def load_cells() -> pl.DataFrame:
    """Contagem de carros por célula no instante TIME."""
    lazy = pl.scan_csv(CSV_FILE, separator=";", has_header=False)
    names = lazy.collect_schema().names()

    if DT is None:
        in_time = (pl.col("tempo") - TIME).abs() < TOL
    else:
        in_time = (pl.col("tempo") <= TIME + TOL) & (
            TIME <= pl.col("tempo") + (pl.col("r") - 1) * DT + TOL
        )

    df = (
        lazy.select(
            pl.col(names[0]).alias("carro_id"),
            pl.col(names[1]).cast(pl.Float64).alias("tempo"),
            pl.col(names[2]).cast(pl.Float64).alias("x"),
            pl.col(names[3]).cast(pl.Float64).alias("y"),
            pl.col(names[4]).cast(pl.Float64).alias("r"),
        )
        .filter(in_time)
        .collect()
    )
    if df.is_empty():
        raise ValueError(f"Não há registros no instante {TIME}.")

    cells = df.group_by(["x", "y"]).agg(pl.len().alias("carros")).sort(["x", "y"])
    return cells


def greedy(cells: pl.DataFrame) -> list[RSU]:
    """Algoritmo Guloso para alocação de RSUs."""
    candidates = []
    for row in cells.iter_rows(named=True):
        if row["carros"] >= 5:
            candidates.append(RSU(x=int(row["x"]), y=int(row["y"]), veh_count=row["carros"]))

    candidates = sorted(candidates, key=lambda item: item.veh_count, reverse=True)
    rsu_alloc = []

    while len(candidates) > 0:
        rsu = candidates.pop(0)
        rsu_alloc.append(rsu)

        # Remove candidatos dentro do raio de exclusão na grade
        candidates = [
            candidato for candidato in candidates
            if math.hypot(rsu.x - candidato.x, rsu.y - candidato.y) > EXCLUSION_RADIUS_CELLS
        ]
    print(f"RSUs Alocadas: {len(rsu_alloc)}")
    return rsu_alloc


def main() -> None:
    streets = load_streets(NET_FILE)
    cells = load_cells()
    rsus = greedy(cells)

    fig, ax = plt.subplots(figsize=(11, 11))

    # 1. Desenha as ruas ao fundo (Cinza claro)
    ax.add_collection(LineCollection(streets, colors="0.75", linewidths=0.3))

    # 2. Desenha todos os carros em Cinza Escuro (#333333)
    car_radius_m = min(CELL_W_M, CELL_H_M) * 0.15
    car_patches = []
    for row in cells.iter_rows(named=True):
        cx = (row["x"] + 0.5) * CELL_W_M
        cy = (row["y"] + 0.5) * CELL_H_M
        car_patches.append(Circle((cx, cy), car_radius_m))

    ax.add_collection(
        PatchCollection(car_patches, facecolor="#333333", edgecolor="none", alpha=0.6)
    )

    # 3. Desenha os Círculos de Cobertura das RSUs (Vermelho translúcido com raio real em metros)
    coverage_patches = []
    rsu_x_coords, rsu_y_coords = [], []

    for rsu in rsus:
        cx = (rsu.x + 0.5) * CELL_W_M
        cy = (rsu.y + 0.5) * CELL_H_M
        rsu_x_coords.append(cx)
        rsu_y_coords.append(cy)
        coverage_patches.append(Circle((cx, cy), RSU_COVERAGE_METERS))

    ax.add_collection(
        PatchCollection(
            coverage_patches,
            facecolor="red",
            edgecolor="darkred",
            linewidth=0.8,
            alpha=0.25
        )
    )

    # 4. Plota o ponto central das RSUs como Bolinhas Vermelhas Sólidas
    ax.scatter(
        rsu_x_coords,
        rsu_y_coords,
        color="red",
        marker="o",
        s=35,
        zorder=5,
        edgecolor="darkred",
        linewidth=0.5,
        label=f"RSUs Alocadas ({len(rsus)})"
    )

    # Ajustes Finais do Gráfico
    ax.set_xlim(0, NET_WIDTH_M)
    ax.set_ylim(0, NET_HEIGHT_M)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title(f"Alocação de RSUs (Greedy) | t = {TIME:.0f} s | Total RSUs: {len(rsus)}")

    # Legenda Personalizada
    ax.legend(
        handles=[
            Patch(facecolor="#333333", alpha=0.6, label="Ocupação de Veículos"),
            Patch(facecolor="red", alpha=0.25, edgecolor="darkred", label=f"Alcance RSU ({RSU_COVERAGE_METERS:.0f}m)"),
            plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="red", markeredgecolor="darkred", markersize=7, label="Unidade RSU"),
        ],
        loc="upper right",
    )

    fig.tight_layout()
    fig.savefig(OUT_FILE, dpi=200)
    print(f"[+] Mapa com RSUs salvo com sucesso em {OUT_FILE}")
    if SHOW:
        plt.show()


if __name__ == "__main__":
    main()