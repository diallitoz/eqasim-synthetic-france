import numpy as np
import pandas as pd
import geopandas as gpd
from tqdm import tqdm
from .candidates import EDUCATION_MAPPING

def configure(context):
    context.stage("synthesis.population.spatial.primary.candidates")
    context.stage("synthesis.population.spatial.commute_distance")
    context.stage("synthesis.population.spatial.home.locations")
    context.stage("synthesis.locations.work")
    context.stage("synthesis.locations.education")

    context.config("education_location_source", "bpe")


def fast_distance_ordering(home_x, home_y, expected_dist, cand_x, cand_y):
    N = len(home_x)
    indices = np.empty(N, dtype=np.int64)
    
    active_cands = np.arange(N)
    
    for i in range(N):
        hx, hy, ed = home_x[i], home_y[i], expected_dist[i]
        
        cx = cand_x[active_cands]
        cy = cand_y[active_cands]
        
        dx = cx - hx
        dy = cy - hy
        dist = np.sqrt(dx*dx + dy*dy)
        cost = np.abs(dist - ed)
        
        best_idx = np.argmin(cost)
        indices[i] = active_cands[best_idx]
        
        last_idx = len(active_cands) - 1
        active_cands[best_idx] = active_cands[last_idx]
        active_cands = active_cands[:last_idx]
        
    return indices

def process(context, purpose, df_persons, df_candidates):
    print(f"[{purpose}] Preparing fast geometric assignment...")
    
    df_persons = df_persons.sort_values("commune_id").reset_index(drop=True)
    df_candidates = df_candidates.sort_values("origin_id").reset_index(drop=True)
    
    home_geoms = gpd.GeoSeries(df_persons["home_location"])
    person_home_x = home_geoms.x.values
    person_home_y = home_geoms.y.values
    person_dist = df_persons["commute_distance"].values
    person_ids = df_persons["person_id"].values
    person_communes = df_persons["commune_id"].values
    
    cand_x = df_candidates["geometry"].x.values
    cand_y = df_candidates["geometry"].y.values
    cand_loc_ids = df_candidates["location_id"].values
    cand_geoms = df_candidates["geometry"].values
    cand_dests = df_candidates["destination_id"].values
    
    out_person_id = np.empty(len(df_persons), dtype=person_ids.dtype)
    out_commune_id = np.empty(len(df_persons), dtype=cand_dests.dtype)
    out_location_id = np.empty(len(df_persons), dtype=cand_loc_ids.dtype)
    out_geometry = np.empty(len(df_persons), dtype=object)

    unique_communes, person_counts = np.unique(person_communes, return_counts=True)
    person_slices = np.insert(np.cumsum(person_counts), 0, 0)
    
    cand_communes = df_candidates["origin_id"].values
    _, cand_counts = np.unique(cand_communes, return_counts=True)
    cand_slices = np.insert(np.cumsum(cand_counts), 0, 0)

    for i in tqdm(range(len(unique_communes)), desc=f"Assigning {purpose}"):
        p_start, p_end = person_slices[i], person_slices[i+1]
        c_start, c_end = cand_slices[i], cand_slices[i+1]
        
        ordered_indices = fast_distance_ordering(
            person_home_x[p_start:p_end],
            person_home_y[p_start:p_end],
            person_dist[p_start:p_end],
            cand_x[c_start:c_end],
            cand_y[c_start:c_end]
        )
        
        global_ordered_indices = c_start + ordered_indices
        
        out_person_id[p_start:p_end] = person_ids[p_start:p_end]
        out_commune_id[p_start:p_end] = cand_dests[global_ordered_indices]
        out_location_id[p_start:p_end] = cand_loc_ids[global_ordered_indices]
        out_geometry[p_start:p_end] = cand_geoms[global_ordered_indices]

    df_result = pd.DataFrame({
        "person_id": out_person_id,
        "commune_id": out_commune_id,
        "location_id": out_location_id,
        "geometry": out_geometry
    })
    
    return df_result

def execute(context):
    data = context.stage("synthesis.population.spatial.primary.candidates")
    df_persons = data["persons"]

    # Separate data set
    df_work = df_persons[df_persons["has_work_trip"]]
    df_education = df_persons[df_persons["has_education_trip"]]

    # Attach home locations
    df_home = context.stage("synthesis.population.spatial.home.locations")

    df_work = pd.merge(df_work, df_home[["household_id", "geometry"]].rename(columns = {
        "geometry": "home_location"
    }), how = "left", on = "household_id")

    df_education = pd.merge(df_education, df_home[["household_id", "geometry"]].rename(columns = {
        "geometry": "home_location"
    }), how = "left", on = "household_id")

    # Attach commute distances
    df_commute_distance = context.stage("synthesis.population.spatial.commute_distance")

    df_work = pd.merge(df_work, df_commute_distance["work"], how = "left", on = "person_id")
    df_education = pd.merge(df_education, df_commute_distance["education"], how = "left", on = "person_id")

    # Attach geometry
    df_locations = context.stage("synthesis.locations.work")[["location_id", "geometry"]]
    df_work_candidates = data["work_candidates"]
    df_work_candidates = pd.merge(df_work_candidates, df_locations, how = "left", on = "location_id")
    df_work_candidates = gpd.GeoDataFrame(df_work_candidates)

    df_locations = context.stage("synthesis.locations.education")[["education_type", "location_id", "geometry"]]
    df_education_candidates = data["education_candidates"]
    df_education_candidates = pd.merge(df_education_candidates, df_locations, how = "left", on = "location_id")
    df_education_candidates = gpd.GeoDataFrame(df_education_candidates)

    # Assign destinations
    df_work = process(context, "work", df_work, df_work_candidates)
    if context.config("education_location_source") == 'bpe':
        df_education = process(context, "education", df_education, df_education_candidates)
    else :
        education = []
        for prefix, education_type in EDUCATION_MAPPING.items():
            education.append(process(context, prefix, df_education[df_education["age_range"]==prefix], df_education_candidates[df_education_candidates["education_type"].isin(education_type)]))
        df_education = pd.concat(education).sort_index()
        
    return df_work, df_education