import pandas as pd
import geopandas as gpd
import zipfile
import py7zr
from pathlib import Path
import numpy as np

"""
This stage loads a file containing all spatial codes in France and how
they can be translated into each other. These are mainly IRIS, commune,
département and région.
"""

def configure(context):
    context.config("data_path")
    context.config("regions", [11])
    context.config("departments", [])
    context.config("codes_path", "codes_2024/reference_IRIS_geo2024.zip")
    context.config("codes_xlsx", "reference_IRIS_geo2024.xlsx")
    context.config("iris_path", "iris_2024")
    context.config("hts_sig_name", "")
    context.config("mobisurvstd.path", "")


def _load_registry(data_path: Path, codes_path: str, codes_xlsx: str) -> pd.DataFrame:
    """Loads and cleans the IRIS codes registry from the zip archive."""
    zip_path = data_path / codes_path
    
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(codes_xlsx) as f:
            df_codes = pd.read_excel(
                f,
                skiprows=5, 
                sheet_name="Emboitements_IRIS",
                dtype={"CODE_IRIS": str, "DEPCOM": str}
            )
            
    df_codes = df_codes[["CODE_IRIS", "DEPCOM", "DEP", "REG"]].rename(columns={
        "CODE_IRIS": "iris_id",
        "DEPCOM": "commune_id",
        "DEP": "departement_id",
        "REG": "region_id"
    }).fillna('0')

    df_codes["iris_id"] = df_codes["iris_id"].astype("category")
    df_codes["commune_id"] = df_codes["commune_id"].astype("category")
    df_codes["departement_id"] = df_codes["departement_id"].astype("category")
    df_codes["region_id"] = df_codes["region_id"].astype(int)
    
    return df_codes


def _find_iris_archive(iris_dir: Path) -> Path:
    """Finds the 7z archive containing the IRIS data."""
    candidates = sorted(list(iris_dir.glob("*.7z")))

    if not candidates:
        raise RuntimeError(f"IRIS data is not available in {iris_dir}")
    if len(candidates) > 1:
        raise RuntimeError(f"Multiple candidates for IRIS are available in {iris_dir}")
        
    return candidates[0]


def _load_iris_shapes(context_path: str, archive_path: Path) -> gpd.GeoDataFrame:
    """Extracts the 7z archive and loads the geopackage (.gpkg) file."""
    with py7zr.SevenZipFile(archive_path) as archive:
        contour_paths = [path for path in archive.getnames() if "LAMB93" in path]
        archive.extract(context_path, contour_paths)
    
    gpkg_paths = [path for path in contour_paths if path.endswith(".gpkg")]

    if len(gpkg_paths) != 1:
        raise RuntimeError("Cannot find exactly one IRIS .gpkg inside the archive. Please report this as an error!")

    gpkg_full_path = Path(context_path) / gpkg_paths[0]
    
    df_iris = gpd.read_file(
        gpkg_full_path, 
        dtype={"code_iris": str, "code_insee": str}
    )[["code_insee", "code_iris", "geometry"]].rename(columns={
        "code_iris": "iris_id",
        "code_insee": "commune_id"
    })

    assert df_iris.crs == "EPSG:2154", f"Unexpected CRS: {df_iris.crs}"

    df_iris["iris_id"] = df_iris["iris_id"].astype("category")
    df_iris["commune_id"] = df_iris["commune_id"].astype("category")
    
    return df_iris


def execute(context) -> pd.DataFrame:
    data_path = Path(context.config("data_path"))
    
    # 1. Load registry (Excel)
    df_codes = _load_registry(
        data_path, 
        context.config("codes_path"), 
        context.config("codes_xlsx")
    )

    # 2. Load shapes (GeoPackage)
    iris_dir = data_path / context.config("iris_path")
    source_path = _find_iris_archive(iris_dir)
    df_iris = _load_iris_shapes(context.path(), source_path)

    # 3. Load HTS area and perform Spatial Join
    hts_area_shp_path = data_path / context.config("mobisurvstd.path")
    requested_hts_file = hts_area_shp_path / "Doc" / "SIG" / context.config("hts_sig_name")
    
    df_requested_hts_area = gpd.read_file(requested_hts_file)

    if df_requested_hts_area.crs is None:
        print("SHP CRS unknow")
        df_requested_hts_area = df_requested_hts_area.set_crs("EPSG:2154")

    elif df_requested_hts_area.crs != "EPSG:2154":
        print("SHP CRS != 2154")
        df_requested_hts_area = df_requested_hts_area.to_crs("EPSG:2154")

    df_iris_intersecting = df_iris.sjoin(
        df_requested_hts_area[["geometry"]], 
        how="inner", 
        predicate="intersects"
    )

    valid_communes = df_iris_intersecting["commune_id"].unique()

    df_iris = df_iris[df_iris["commune_id"].isin(valid_communes)]

    # A 'left sjoin' adds an 'index_right' column which is often good to clean up
    #if "index_right" in df_iris.columns:
        #df_iris = df_iris.drop(columns=["index_right"])

    # 4. Merge codes and geometry
    df_codes = pd.merge(df_codes, df_iris[["iris_id", "commune_id"]], how="right", on=["iris_id", "commune_id"])
    mapping_path = Path(context.config("data_path")) / "rp_2022/table-appartenance-geo-communes-22.zip"
    
    # On lit le fichier Excel en ciblant la feuille "COM" et la bonne ligne d'en-tête
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
            
    '''
    df_mapping = pd.read_excel(
        mapping_path,
        sheet_name="COM",
        header=5,
        usecols=["CODGEO", "CANOV"], # On charge uniquement les 2 colonnes nécessaires
        dtype={"CODGEO": str, "CANOV": str}
    )
    '''
    
    # 6. Renommer les colonnes pour préparer la jointure
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
    
    
    # 5. Filtering based on requested areas
    requested_regions = [int(r) for r in context.config("regions") if r]
    requested_departments = [str(d) for d in context.config("departments") if d]

    if requested_regions:
        df_codes = df_codes[df_codes["region_id"].isin(requested_regions)]

    if requested_departments:
        df_codes = df_codes[df_codes["departement_id"].isin(requested_departments)]

    # Clean up unused categories
    for col in ["iris_id", "commune_id", "departement_id"]:
        if df_codes[col].dtype.name == "category":
            df_codes[col] = df_codes[col].cat.remove_unused_categories()
        else:
            df_codes[col] = df_codes[col].astype("category")
    
    # Clean nan departement
    nan_dep = df_codes["departement_id"].isna()
    if np.count_nonzero(nan_dep) > 0:
        print("Some departements are unknow for these communes:", df_codes[nan_dep]["commune_id"].unique())
        df_codes = df_codes[~df_codes["departement_id"].isna()]
    
    return df_codes


def validate(context) -> int:
    codes_full_path = Path(context.config("data_path")) / context.config("codes_path")
    
    if not codes_full_path.exists():
        raise RuntimeError("Spatial reference codes are not available")

    # Pathlib allows getting the file size directly via stat()
    return codes_full_path.stat().st_size