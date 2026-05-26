import data.spatial.utils as spatial_utils
import numpy as np
import pandas as pd
import geopandas as gpd

def configure(context):
    context.stage("synthesis.population.spatial.home.zones")
    context.stage("synthesis.locations.home.locations")
    context.config("home_location_source", "addresses")
    context.config("random_seed")

def execute(context):
    random = np.random.default_rng(context.config("random_seed"))

    df_homes = context.stage("synthesis.population.spatial.home.zones")
    df_locations = context.stage("synthesis.locations.home.locations")
                    
    print("Sampling home locations vectorially...")

    loc_data = {}
    locations_grouped = df_locations.groupby("iris_id", observed=True)
    
    for iris_id, group in locations_grouped:
        weights = group["weight"].values
        total_weight = weights.sum()
        
        if total_weight > 0:
            probs = weights / total_weight
        else:
            probs = np.ones(len(group)) / len(group)
        
        loc_data[iris_id] = {
            "geom": group["geometry"].values,
            "loc_id": group["home_location_id"].values,
            "probs": probs,
            "n_locs": len(group)
        }

    df_homes = df_homes.sort_values("iris_id").reset_index(drop=True)
    
    geoms = np.empty(len(df_homes), dtype=object)
    loc_ids = np.empty(len(df_homes), dtype=object)

    homes_grouped = df_homes.groupby("iris_id", observed=True)
    
    for iris_id, indices in homes_grouped.groups.items():
        n_homes = len(indices)
        
        if iris_id in loc_data:
            data = loc_data[iris_id]
            
            chosen_idx = random.choice(data["n_locs"], size=n_homes, p=data["probs"])
            
            geoms[indices] = data["geom"][chosen_idx]
            loc_ids[indices] = data["loc_id"][chosen_idx]
        else:
            raise RuntimeError(f"No locations found for IRIS {iris_id}")

    df_homes["geometry"] = geoms
    df_homes["home_location_id"] = loc_ids
    
    df_homes = gpd.GeoDataFrame(df_homes, crs=df_locations.crs)

    out = ["household_id", "commune_id", "home_location_id", "geometry"]
    return df_homes[out]