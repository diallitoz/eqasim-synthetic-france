import os
import pandas as pd
import zipfile
import geopandas as gpd

"""
This stages loads a file containing all spatial codes in France and how
they can be translated into each other. These are mainly IRIS, commune,
departement and région.
"""

def configure(context):
    context.config("data_path")

    context.config("regions", [11])
    context.config("departments", [])
    context.config("codes_path", "codes_2024/reference_IRIS_geo2024.zip")
    context.config("codes_xlsx", "reference_IRIS_geo2024.xlsx")
    context.stage("data.spatial.iris_raw")
    context.config("table_appart_path", "rp_2022/table-appartenance-geo-communes-22.zip")
    context.config("mobisurvstd.path")
    context.config("hts_sig_name")

def execute(context):
    # Load IRIS registry
    with zipfile.ZipFile(
        "{}/{}".format(context.config("data_path"), context.config("codes_path"))) as archive:
        with archive.open(context.config("codes_xlsx")) as f:
            df_codes = pd.read_excel(f,
                skiprows = 5, sheet_name = "Emboitements_IRIS",dtype={"CODE_IRIS":str,"DEPCOM":str}
            )[["CODE_IRIS", "DEPCOM", "DEP", "REG"]].rename(columns = {
                "CODE_IRIS": "iris_id",
                "DEPCOM": "commune_id",
                "DEP": "departement_id",
                "REG": "region_id"
            }).fillna('0')

    df_codes["iris_id"] = df_codes["iris_id"].astype("category")
    df_codes["commune_id"] = df_codes["commune_id"].astype("category")
    df_codes["departement_id"] = df_codes["departement_id"].astype("category")
    df_codes["region_id"] = df_codes["region_id"].astype(int)

    # 2. Load shapes (GeoPackage)
    df_iris = context.stage("data.spatial.iris_raw")
    
    # 3. Load HTS area and perform Spatial Join
    hts_area_shp_path = os.path.join(context.config("data_path"), context.config("mobisurvstd.path"))
    requested_hts_file = os.path.join(hts_area_shp_path, "Doc", "SIG", context.config("hts_sig_name"))
    df_requested_hts_area = gpd.read_file(requested_hts_file)

    if df_requested_hts_area.crs is None:
        print("SHP CRS unknow")
        df_requested_hts_area = df_requested_hts_area.set_crs("EPSG:2154")

    elif df_requested_hts_area.crs != "EPSG:2154":
        print("SHP CRS != 2154")
        df_requested_hts_area = df_requested_hts_area.to_crs("EPSG:2154")

    #df_iris_intersecting = df_iris.sjoin(
    #    df_requested_hts_area[["geometry"]], 
    #    how="inner", 
    #    predicate="intersects"
    #)

    df_iris_points = df_iris.copy()
    df_iris_points["geometry"] = df_iris.geometry.representative_point()

    df_iris_intersecting = df_iris_points.sjoin(
        df_requested_hts_area[["geometry"]], 
        how="inner", 
        predicate="within"  # or "intersects"
    )

    valid_communes = df_iris.loc[df_iris_intersecting.index, "commune_id"].unique()
    df_iris = df_iris[df_iris["commune_id"].isin(valid_communes)]

    #valid_communes = df_iris_intersecting["commune_id"].unique()

    #df_iris = df_iris[df_iris["commune_id"].isin(valid_communes)]

    # 4. Merge codes and geometry
    df_codes = pd.merge(df_codes, df_iris[["iris_id", "commune_id"]], how="right", on=["iris_id", "commune_id"])

    # 5. Add CANTVILLE from Table Appartenance
    mapping_path = "{}/{}".format(context.config("data_path"), context.config("table_appart_path"))
    with zipfile.ZipFile(mapping_path) as archive:
        with archive.open("table-appartenance-geo-communes-2022.xlsx") as f:
            df_mapping = pd.read_excel(
                f,
                skiprows=5, 
                sheet_name="COM",
                usecols=["CODGEO", "CANOV"],
                dtype={"CODGEO": str, "CANOV": str},
                engine="calamine"
            )
            
    df_mapping = df_mapping.rename(columns={
        "CODGEO": "commune_id", 
        "CANOV": "CANTVILLE"
    })

    df_codes = pd.merge(
        df_codes, 
        df_mapping,
        on="commune_id",
        how="left"
    )

    # Filter zones - No longer necessary
    requested_regions = list(map(int, context.config("regions")))
    requested_departments = list(map(str, context.config("departments")))

    if len(requested_regions) > 0:
        df_codes = df_codes[df_codes["region_id"].isin(requested_regions)]

    if len(requested_departments) > 0:
        df_codes = df_codes[df_codes["departement_id"].isin(requested_departments)]

    df_codes["iris_id"] = df_codes["iris_id"].astype("category")
    df_codes["commune_id"] = df_codes["commune_id"].astype("category")
    df_codes["departement_id"] = df_codes["departement_id"].astype("category")

    df_codes["iris_id"] = df_codes["iris_id"].cat.remove_unused_categories()
    df_codes["commune_id"] = df_codes["commune_id"].cat.remove_unused_categories()
    df_codes["departement_id"] = df_codes["departement_id"].cat.remove_unused_categories()

    return df_codes

def validate(context):
    if not os.path.exists("%s/%s" % (context.config("data_path"), context.config("codes_path"))):
        raise RuntimeError("Spatial reference codes are not available")

    return os.path.getsize("%s/%s" % (context.config("data_path"), context.config("codes_path")))
