import shutil
import gzip
import geopandas as gpd
import pandas as pd
import shapely.geometry as geo
import os, datetime, json
import sqlite3
import math
import numpy as np
import gc
from analysis.synthesis.population import ANALYSIS_FOLDER

def configure(context):
    context.stage("synthesis.population.enriched")
    context.stage("synthesis.population.activities")
    context.stage("synthesis.population.trips")
    context.stage("synthesis.vehicles.vehicles")
    context.stage("synthesis.population.spatial.locations")
    context.stage("documentation.meta_output")

    context.config("output_path")
    context.config("output_prefix", "ile_de_france_")
    context.config("output_formats", ["csv", "parquet"])
    context.config("sampling_rate")
    context.config("extra_enriched_attributes", [])

    if context.config("mode_choice", False):
        context.stage("matsim.simulation.prepare")


def validate(context):
    output_path = context.config("output_path")
    if not os.path.isdir(output_path):
        raise RuntimeError("Output directory must exist: %s" % output_path)

def clean_gpkg(path):
    '''Make GPKG files time and OS independent.'''
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    for table_name, min_x, min_y, max_x, max_y in cur.execute("SELECT table_name, min_x, min_y, max_x, max_y FROM gpkg_contents"):
        cur.execute(
            "UPDATE gpkg_contents SET last_change='2000-01-01T00:00:00Z', min_x=?, min_y=?, max_x=?, max_y=? WHERE table_name=?",
            (math.floor(min_x), math.floor(min_y), math.ceil(max_x), math.ceil(max_y), table_name)
        )
    conn.commit()
    conn.close()

def get_missing_formats(base_path, formats):
    missing = []
    for fmt in formats:
        if fmt in ["csv", "parquet", "geoparquet", "gpkg"]:
            if not os.path.exists(f"{base_path}.{fmt}"):
                missing.append(fmt)
    return missing

def write_data(df, base_path, formats):
    if "csv" in formats:
        df.to_csv(f"{base_path}.csv", sep=";", index=None, lineterminator="\n")
    if "parquet" in formats:
        df.to_parquet(f"{base_path}.parquet")
    if "gpkg" in formats:
        df.to_file(f"{base_path}.gpkg", driver="GPKG")
        clean_gpkg(f"{base_path}.gpkg")
    if "geoparquet" in formats:
        df.to_parquet(f"{base_path}.geoparquet")


def execute(context):
    output_path = context.config("output_path")
    prefix = context.config("output_prefix")
    formats = context.config("output_formats")
    
    tab_fmts = [f for f in formats if f in ["csv", "parquet"]]
    sp_fmts = [f for f in formats if f in ["gpkg", "geoparquet"]]

    #Step 1: Tabulary data
    
    #PERSONS
    base_pers = f"{output_path}/{prefix}persons"
    miss_pers = get_missing_formats(base_pers, tab_fmts)
    
    df_persons = context.stage("synthesis.population.enriched")
    df_person_mapping = df_persons[["person_id", "household_id"]].copy()

    if miss_pers:
        print("[1/6] Exporting persons...")
        df_p_exp = df_persons.rename(columns={"has_license": "has_driving_license"})
        cols = [
            "person_id", "household_id", "age", "employed", "studies", "sex", "socioprofessional_class",
            "professional_activity", "has_driving_license", "has_pt_subscription", "census_person_id", "hts_id"
        ] + context.config("extra_enriched_attributes")
        
        write_data(df_p_exp[cols], base_pers, miss_pers)
        del df_p_exp
    else:
        print("[1/6] Skipping persons (already exists)")
        
    del df_persons
    gc.collect()

    base_act = f"{output_path}/{prefix}activities"
    base_hh = f"{output_path}/{prefix}households"
    
    miss_act = get_missing_formats(base_act, tab_fmts)
    miss_hh = get_missing_formats(base_hh, tab_fmts)
    miss_sp_act = get_missing_formats(base_act, sp_fmts)
    
    df_home_acts = None
    if miss_act or miss_hh or miss_sp_act:
        print("[2/6] Processing activities...")
        df_act = context.stage("synthesis.population.activities").rename(columns={"trip_index": "following_trip_index"})
        df_act = pd.merge(df_act, df_person_mapping, on="person_id")
        
        df_act["preceding_trip_index"] = df_act["following_trip_index"].shift(1)
        df_act.loc[df_act["is_first"], "preceding_trip_index"] = -1
        df_act["preceding_trip_index"] = df_act["preceding_trip_index"].astype(np.int32)
        
        df_loc_no_geom = context.stage("synthesis.population.spatial.locations")[[
            "person_id", "iris_id", "commune_id","departement_id","region_id","activity_index"
        ]]
        df_act = pd.merge(df_act, df_loc_no_geom, how="left", on=["person_id", "activity_index"])
        del df_loc_no_geom
        gc.collect()

        act_cols = [
            "person_id", "household_id", "activity_index", "iris_id", "commune_id","departement_id","region_id", 
            "preceding_trip_index", "following_trip_index", "purpose", "start_time", "end_time", "is_first", "is_last"
        ]

        if miss_act:
            print("      Writing tabular activities...")
            write_data(df_act[act_cols], base_act, miss_act)
            
        if miss_hh:
            df_home_acts = df_act[df_act["purpose"] == "home"][["household_id", "iris_id", "commune_id","departement_id","region_id"]].drop_duplicates("household_id")
            
        if miss_sp_act:
            df_act[act_cols].to_parquet(f"{output_path}/temp_activities.parquet")

        del df_act
        gc.collect()
    else:
        print("[2/6] Skipping activities (already exists)")
        
    del df_person_mapping
    gc.collect()

    if miss_hh:
        print("[3/6] Exporting households...")
        df_hh = context.stage("synthesis.population.enriched").rename(columns={"household_income": "income"}).drop_duplicates("household_id")
        df_hh = pd.merge(df_hh, df_home_acts, how="left")
        del df_home_acts
        
        hh_cols = [
            "household_id","iris_id", "commune_id", "departement_id","region_id",
            "car_availability", "bike_availability", "use_motorcycle",
            "number_of_cars", "number_of_motorcycles", "number_of_vehicles", "number_of_bikes",
            "income", "census_household_id"
        ]
        write_data(df_hh[hh_cols], base_hh, miss_hh)
        del df_hh
        gc.collect()
    else:
        print("[3/6] Skipping households (already exists)")


    base_vtype = f"{output_path}/{prefix}vehicle_types"
    base_veh = f"{output_path}/{prefix}vehicles"
    miss_vtype = get_missing_formats(base_vtype, tab_fmts)
    miss_veh = get_missing_formats(base_veh, tab_fmts)

    if miss_vtype or miss_veh:
        print("[4/6] Exporting vehicles...")
        df_vt, df_v = context.stage("synthesis.vehicles.vehicles")
        if miss_vtype: write_data(df_vt, base_vtype, miss_vtype)
        if miss_veh: write_data(df_v, base_veh, miss_veh)
        del df_vt, df_v
        gc.collect()
    else:
        print("[4/6] Skipping vehicles (already exists)")


    
    base_trips = f"{output_path}/{prefix}trips"
    miss_trips = get_missing_formats(base_trips, tab_fmts)
    miss_sp_trips = get_missing_formats(base_trips, sp_fmts)

    if miss_trips or miss_sp_trips:
        print("[5/6] Processing trips...")
        df_trips = context.stage("synthesis.population.trips").rename(columns={"is_first_trip": "is_first", "is_last_trip": "is_last"})
        df_trips["preceding_activity_index"] = df_trips["trip_index"]
        df_trips["following_activity_index"] = df_trips["trip_index"] + 1

        trip_cols = [
            "person_id", "trip_index", "preceding_activity_index", "following_activity_index",
            "departure_time", "arrival_time", "preceding_purpose", "following_purpose",
            "is_first", "is_last"
        ]
        if "mode" in df_trips: trip_cols.append("mode")

        if context.config("mode_choice"):
            trips_path = "%s/mode_choice/output_trips.csv" % context.path("matsim.simulation.prepare")
            if not os.path.exists(trips_path):
                trips_path += ".gz"
            
            df_mode_choice = pd.read_csv(trips_path, delimiter=";").rename(columns={"person_trip_id": "trip_index"})
            columns_to_keep = ["person_id", "trip_index"] + [c for c in df_trips.columns if c not in df_mode_choice.columns]
            df_trips = pd.merge(df_trips[columns_to_keep], df_mode_choice, on=["person_id", "trip_index"], how="left", validate="one_to_one")
            
            if "mode" not in trip_cols: trip_cols.append("mode")
            assert not np.any(df_trips["mode"].isna())
            del df_mode_choice

            if miss_trips:
                for leg_type in ["pt_legs", "legs"]:
                    src_path = f"{context.path('matsim.simulation.prepare')}/mode_choice/output_{leg_type}.csv"
                    if not os.path.exists(src_path): src_path += ".gz"
                    dest_path = f"{output_path}/{prefix}{leg_type}.csv"
                    
                    if src_path.endswith(".gz"):
                        with gzip.open(src_path, "rb") as f_in, open(dest_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    else:
                        shutil.copy(src_path, dest_path)

        if miss_trips:
            print("      Writing tabular trips...")
            write_data(df_trips[trip_cols], base_trips, miss_trips)
            
        if miss_sp_trips:
            df_trips[trip_cols].to_parquet(f"{output_path}/temp_trips.parquet")
            
        del df_trips
        gc.collect()
    else:
        print("[5/6] Skipping trips (already exists)")



    #Step 2: Spatial data
    
    base_homes = f"{output_path}/{prefix}homes"
    base_commutes = f"{output_path}/{prefix}commutes"
    
    miss_sp_homes = get_missing_formats(base_homes, sp_fmts)
    miss_sp_commutes = get_missing_formats(base_commutes, sp_fmts)

    if miss_sp_act or miss_sp_homes or miss_sp_commutes or miss_sp_trips:
        print("[6/6] Processing spatial geometries (High RAM Zone)...")
        df_locations = context.stage("synthesis.population.spatial.locations")
        crs_val = df_locations.crs if hasattr(df_locations, "crs") else "EPSG:2154"
        
        cols_to_string = ["location_id", "purpose", "departement_id", "commune_id", "iris_id"]
        for col in cols_to_string:
            if col in df_locations.columns:
                df_locations[col] = df_locations[col].astype(str)
        print(df_locations)
        if miss_sp_act:
            print("      Exporting spatial activities...")
            df_act_sp = pd.read_parquet(f"{output_path}/temp_activities.parquet")
            os.remove(f"{output_path}/temp_activities.parquet")
            df_act_sp = pd.merge(df_act_sp, df_locations[["person_id", "activity_index", "geometry"]], how="left", on=["person_id", "activity_index"])
            
            df_act_sp = gpd.GeoDataFrame(df_act_sp, crs=crs_val)
            df_act_sp = df_act_sp.astype({'purpose': 'str', "departement_id": 'str'})
            write_data(df_act_sp, base_act, miss_sp_act)
            del df_act_sp
            gc.collect()

        """
        if miss_sp_homes:
            print("      Exporting spatial homes...")
            purpose_col = "purpose" if "purpose" in df_locations else "activity_index"
            val_to_match = "home" if purpose_col == "purpose" else 0
            
            df_homes = df_locations[df_locations[purpose_col] == val_to_match].drop_duplicates("household_id")
            df_homes = df_homes[["household_id","iris_id", "commune_id","departement_id","region_id", "geometry"]]
            df_homes = gpd.GeoDataFrame(df_homes, crs=crs_val)
            write_data(df_homes, base_homes, miss_sp_homes)
            del df_homes
            gc.collect()
        """
        if miss_sp_commutes:
            print("      Exporting spatial commutes...")
            purpose_col = "purpose" if "purpose" in df_locations else "activity_index"
            
            df_h = df_locations[df_locations[purpose_col] == ("home" if purpose_col == "purpose" else 0)].drop_duplicates("person_id")[["person_id", "geometry"]].rename(columns={"geometry": "home_geometry"})
            df_w = df_locations[df_locations[purpose_col] == ("work" if purpose_col == "purpose" else 1)].drop_duplicates("person_id")[["person_id", "geometry"]].rename(columns={"geometry": "work_geometry"})
            
            df_c = pd.merge(df_h, df_w, on="person_id", how="inner")
            del df_h, df_w
            gc.collect()

            df_c["geometry"] = gpd.GeoSeries([
                geo.LineString(od) if hasattr(od[0], 'x') and hasattr(od[1], 'x') else None
                for od in zip(df_c["home_geometry"], df_c["work_geometry"])
            ], crs=crs_val)
            
            df_c = df_c.dropna(subset=["geometry"]).drop(columns=["home_geometry", "work_geometry"])
            df_c = gpd.GeoDataFrame(df_c, crs=crs_val)
            write_data(df_c, base_commutes, miss_sp_commutes)
            del df_c
            gc.collect()

        if miss_sp_trips:
            print("      Exporting spatial trips...")
            df_t = pd.read_parquet(f"{output_path}/temp_trips.parquet")
            os.remove(f"{output_path}/temp_trips.parquet")

            df_t = pd.merge(df_t, df_locations[["person_id", "activity_index", "geometry"]].rename(columns={"activity_index": "preceding_activity_index", "geometry": "preceding_geometry"}), how="left", on=["person_id", "preceding_activity_index"])
            df_t = pd.merge(df_t, df_locations[["person_id", "activity_index", "geometry"]].rename(columns={"activity_index": "following_activity_index", "geometry": "following_geometry"}), how="left", on=["person_id", "following_activity_index"])
            
            del df_locations
            gc.collect()

            df_t["geometry"] = gpd.GeoSeries([
                geo.LineString(od) if hasattr(od[0], 'x') and hasattr(od[1], 'x') else None
                for od in zip(df_t["preceding_geometry"], df_t["following_geometry"])
            ], crs=crs_val)
            
            df_t = df_t.drop(columns=["preceding_geometry", "following_geometry"]).dropna(subset=["geometry"])
            df_t = gpd.GeoDataFrame(df_t, crs=crs_val)
            
            df_t["following_purpose"] = df_t["following_purpose"].astype(str)
            df_t["preceding_purpose"] = df_t["preceding_purpose"].astype(str)
            if "mode" in df_t:
                df_t["mode"] = df_t["mode"].astype(str)

            write_data(df_t, base_trips, miss_sp_trips)
            del df_t
            gc.collect()
    else:
        print("[6/6] Skipping spatial geometries (already exists or not requested)")
        
    print("Export complet !")