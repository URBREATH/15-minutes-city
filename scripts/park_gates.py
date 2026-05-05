import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, LineString
from typing import Optional
from scripts.logger import logger


def _ensure_unique_id(gdf: gpd.GeoDataFrame, col: str = "unique_id") -> gpd.GeoDataFrame:
    if gdf is None or gdf.empty:
        return gdf
    if col in gdf.columns:
        return gdf
    out = gdf.copy()
    out[col] = range(1, len(out) + 1)
    return out


def _empty_gdf(columns, crs):
    return gpd.GeoDataFrame(columns=columns, geometry="geometry", crs=crs)



        
def gates_a(
    green: gpd.GeoDataFrame,
    gates: gpd.GeoDataFrame,
    id_green_area: str,
    buffer_m: float = 10.0,
    out_path: Optional[str] = None,
    layer_name: str = "gates_a"
) -> gpd.GeoDataFrame:

    crs = green.crs if green is not None else None

    if green is None or green.empty or gates is None or gates.empty:
        return _empty_gdf(["unique_id", id_green_area, "GATE_A", "geometry"], crs)

    green = _ensure_unique_id(green, col=id_green_area)

    # buffer sui parchi
    green_buf = green[[id_green_area, "geometry"]].copy()

   
    green_buf["geometry"] = green_buf.geometry.buffer(float(buffer_m))

    # punti entro buffer
    sel = gpd.sjoin(gates, green_buf, predicate="within", how="inner")
    if sel.empty:
        return _empty_gdf(["unique_id", id_green_area, "GATE_A", "geometry"], crs)

    sel = sel.drop(columns=[c for c in sel.columns if c.startswith("index_")], errors="ignore")

    # nearest join
    nearest = gpd.sjoin_nearest(
        sel,
        green[[id_green_area, "geometry"]],
        how="left",
        max_distance=float(buffer_m)
    )

    def _gate_a(row):
        barrier = str(row.get("barrier") or "").strip().lower()
        entrance = str(row.get("entrance") or "").strip().lower()
    
        if barrier in ("gate", "entrance") or entrance == "yes":
            return "A"
        return None

    nearest["GATE_A"] = nearest.apply(_gate_a, axis=1)
    nearest = _ensure_unique_id(nearest, col="unique_id")

    out = gpd.GeoDataFrame(
        nearest[["unique_id", id_green_area, "GATE_A", "geometry"]],
        geometry="geometry",
        crs=crs
    )

    return out
    
def gates_b(
    green: gpd.GeoDataFrame,
    streets: gpd.GeoDataFrame,
    id_green_area: str,
    out_path: Optional[str] = None,
    layer_name: str = "gates_b"
) -> gpd.GeoDataFrame:

    crs = green.crs if green is not None else None

    if green is None or green.empty or streets is None or streets.empty:
        return _empty_gdf([id_green_area, "GATE_B", "geometry"], crs)

    green = _ensure_unique_id(green, col=id_green_area)

    boundaries = green[[id_green_area, "geometry"]].copy()
    boundaries["geometry"] = boundaries.geometry.boundary
    boundaries = boundaries[~boundaries.geometry.is_empty & boundaries.geometry.notna()]

    if boundaries.empty:
        return _empty_gdf([id_green_area, "GATE_B", "geometry"], crs)

    streets_sel = gpd.sjoin(
        streets,
        green[[id_green_area, "geometry"]],
        predicate="intersects",
        how="inner"
    )

    if streets_sel.empty:
        return _empty_gdf([id_green_area, "GATE_B", "geometry"], crs)

    streets_sel = streets_sel.drop(columns=[c for c in streets_sel.columns if c.startswith("index_")], errors="ignore")

    inter = gpd.overlay(streets_sel, boundaries, how="intersection", keep_geom_type=False)
    inter = inter[inter.geometry.type.isin(["Point", "MultiPoint"])].explode(index_parts=False)

    if inter.empty:
        return _empty_gdf([id_green_area, "GATE_B", "geometry"], crs)

    inter["GATE_B"] = "B"

    out = gpd.GeoDataFrame(
        inter[[id_green_area, "GATE_B", "geometry"]],
        geometry="geometry",
        crs=crs
    )

    return out
    
    
def _points_along_line(line: LineString, step: float) -> list[Point]:
    if line.is_empty or line.length == 0:
        return []
    d = 0.0
    pts = []
    while d < line.length:
        pts.append(line.interpolate(d))
        d += step
    pts.append(line.interpolate(line.length))
    return pts


def gates_c(
    green: gpd.GeoDataFrame,
    id_green_area: str,
    distance_m: float = 100.0,
    out_path: Optional[str] = None,
    layer_name: str = "gates_c"
) -> gpd.GeoDataFrame:

    crs = green.crs if green is not None else None
    logger.info('sono qui')
    if green is None or green.empty:
        return _empty_gdf([id_green_area, "GATE_C", "geometry"], crs)

    green = _ensure_unique_id(green, col=id_green_area)

    boundaries = green[[id_green_area, "geometry"]].copy()
    boundaries["geometry"] = boundaries.geometry.boundary
    boundaries = boundaries[~boundaries.geometry.is_empty & boundaries.geometry.notna()]

    records = []
    for _, row in boundaries.iterrows():
        gid = row[id_green_area]
        geom = row.geometry

        if geom.geom_type == "LineString":
            lines = [geom]
        elif geom.geom_type == "MultiLineString":
            lines = list(geom.geoms)
        else:
            continue

        for ln in lines:
            for p in _points_along_line(ln, float(distance_m)):
                records.append({id_green_area: gid, "GATE_C": "C", "geometry": p})

    if not records:
        return _empty_gdf([id_green_area, "GATE_C", "geometry"], crs)

    out = gpd.GeoDataFrame(records, geometry="geometry", crs=crs)
    return out
