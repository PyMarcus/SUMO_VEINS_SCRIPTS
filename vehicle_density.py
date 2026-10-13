import polars as pl
from collections import defaultdict
from scipy.spatial import cKDTree

SCHEMA = {
    "carro_id": pl.Int64,
    "tempo": pl.Float64,
    "x": pl.Float64,
    "y": pl.Float64,
    "r": pl.Float64,
}


def load_snapshot(file_name: str, time: float, tol: float = 1e-6) -> pl.DataFrame:
    return (
        pl.scan_csv(
            file_name,
            separator=";",
            has_header=False,
            new_columns=list(SCHEMA),
            schema_overrides=SCHEMA,
        )
        .filter((pl.col("tempo") - time).abs() < tol)
        .select(["carro_id", "x", "y"])
        .collect()
    )


def discovery_neighbors(df: pl.DataFrame, radius: float = 0.9) -> dict:
    ids = df["carro_id"].to_list()
    graph = {i: [] for i in ids}
    if len(ids) < 2:
        return graph

    tree = cKDTree(df.select(["x", "y"]).to_numpy())
    pairs = tree.query_pairs(r=radius, output_type="ndarray")  # (n_pairs, 2), i < j

    for i, j in pairs:
        graph[ids[i]].append(ids[j])
        graph[ids[j]].append(ids[i])

    return graph


if __name__ == "__main__":
    df = load_snapshot("TRACE-0-ordenado.csv", time=32331.0) # 32331 full 21611
    neighbors = discovery_neighbors(df)
    for k, v in neighbors.items():
        print(f"Car: {k} -> {len(v)}")