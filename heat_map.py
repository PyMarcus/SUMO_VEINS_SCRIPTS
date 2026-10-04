import polars as pl
import numpy as np
import matplotlib.pyplot as plt

df = pl.read_csv("TRACE-output.csv", separator=";")

GRID = 100
matriz_calor = np.zeros((GRID, GRID))


df_agregado = df.group_by(["x", "y"]).agg(
    (pl.col("r").sum() * 1800).alias("tempo_total_segundos")
)

for row in df_agregado.iter_rows(named=True):
    gx, gy = int(row["x"]), int(row["y"])
    matriz_calor[gy, gx] = row["tempo_total_segundos"]

# 5. Renderizar o Heatmap
plt.figure(figsize=(10, 8))
plt.imshow(matriz_calor, cmap='hot', origin='lower', interpolation='nearest')
plt.colorbar(label="Segundos de Ocupação Acumulada")
plt.title("Heatmap de Congestionamento na Grade")
plt.xlabel("Célula X")
plt.ylabel("Célula Y")
plt.show()