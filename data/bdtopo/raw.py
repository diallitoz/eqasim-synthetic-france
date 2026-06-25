import pyogrio
import pandas as pd
import os
import geopandas as gpd
import py7zr
import glob
import numpy as np

"""
This stage loads the raw data from the French building registry (BD-TOPO).
"""
 
def configure(context):
    context.config("data_path")
    context.config("bdtopo_path", "bdtopo_idf")

    context.stage("data.spatial.departments")

def get_department_string(department_id):
    department_id = str(department_id)

    if len(department_id) == 2:
        return "0{}".format(department_id)
    elif len(department_id) == 3:
        return department_id
    else:
        raise RuntimeError("Department identifier should have at least two characters")

def execute(context):
    df_departments = context.stage("data.spatial.departments")
    print("Expecting data for {} : {} departments".format(len(df_departments), df_departments["departement_id"].unique()))
    
    source_paths = find_bdtopo("{}/{}".format(context.config("data_path"), context.config("bdtopo_path")))

    df_bdtopo = []
    known_ids = set()

    for source_path in source_paths:
        print("Loading {}".format(source_path.split("/")[-1]))
        geometry_path = None

        with py7zr.SevenZipFile(source_path) as archive:
            # Find the path inside the archive
            internal_path = [path for path in archive.getnames() if path.endswith(".gpkg")]
            
            if len(internal_path) != 1:
                print("  Skipping: No unambiguous geometry source found!")

            else:
                print("  Extracting ...")
                archive.extract(context.path(), [internal_path[0]])
                geometry_path = "{}/{}".format(context.path(), internal_path[0])

        if geometry_path is not None:
            df_buildings = pyogrio.read_dataframe(geometry_path, layer = "batiment", columns = [
                "cleabs", "nombre_de_logements", "usage_1"]).to_crs("EPSG:2154")
            
            df_buildings["building_id"] = df_buildings["cleabs"].apply(lambda x: int(x[8:]))
            df_buildings["housing"] = df_buildings["nombre_de_logements"].fillna(0).astype(int)

            df_buildings["centroid"] = df_buildings["geometry"].centroid
            df_buildings = df_buildings.set_geometry("centroid")

            print("  Filtering ...")

            initial_count = len(df_buildings)
            df_buildings = df_buildings[~df_buildings["building_id"].isin(known_ids)]
            final_count = len(df_buildings)
            print("    {}/{} filtered duplicates".format(initial_count - final_count, initial_count))

            initial_count = len(df_buildings)
            df_buildings = gpd.sjoin(df_buildings, df_departments, predicate = "within")
            final_count = len(df_buildings)
            print("    {}/{} filtered spatially".format(initial_count - final_count, initial_count))
            

            
            print(df_buildings["usage_1"].value_counts())
            print(df_buildings["housing"].value_counts())
            is_dept_08 = (df_buildings["departement_id"] == "08")
            mask_08 = is_dept_08 & df_buildings["usage_1"].isin(["R\u00e9sidentiel", "Indiff\u00e9renci\u00e9"])
            #df_buildings = df_buildings[df_buildings["usage_1"].isin(["R\u00e9sidentiel", "Indiff\u00e9renci\u00e9"])]
            #Pour les autres : Logements > 0
            mask_others = ~is_dept_08 & (df_buildings["housing"] > 0)
            initial_count = len(df_buildings)
            #df_buildings = df_buildings[df_buildings["housing"] > 0]
            df_buildings = df_buildings[mask_08 | mask_others]
            final_count = len(df_buildings)
            print("    {}/{} filtered by dwellings".format(initial_count - final_count, initial_count))
            
            df_buildings["department_id"] = df_buildings["departement_id"]
            df_buildings = df_buildings.set_geometry("geometry")

            df_bdtopo.append(df_buildings[["building_id", "housing", "department_id", "geometry"]])
            known_ids |= set(df_buildings["building_id"].unique())

            os.remove(geometry_path)

    df_bdtopo = pd.concat(df_bdtopo)
    print(df_bdtopo["department_id"].value_counts())

    for department_id in df_departments["departement_id"].values:
        if(np.count_nonzero(df_bdtopo["department_id"] == department_id) > 0):
            print("Departement non conforme", department_id , np.count_nonzero(df_bdtopo["department_id"] == department_id))
            #print(df_bdtopo["department_id"].value_counts().head(10))
            print(df_bdtopo[df_bdtopo["department_id"] == department_id])
            print(df_bdtopo[df_bdtopo["department_id"] == department_id].info())
            print(df_bdtopo["housing"].value_counts())
        else:
            print("Non conform departement:", department_id)
        #assert np.count_nonzero(df_bdtopo["department_id"] == department_id) > 0

    return df_bdtopo[["building_id", "housing", "geometry"]]

def find_bdtopo(path):
    candidates = sorted(list(glob.glob("{}/*.7z".format(path))))

    if len(candidates) == 0:
        raise RuntimeError("BD TOPO data is not available in {}".format(path))
    
    return candidates

def validate(context):
    paths = find_bdtopo("{}/{}".format(context.config("data_path"), context.config("bdtopo_path")))
    return sum([os.path.getsize(path) for path in paths])
