# Gathering the data

To create the scenario, synthetic population, a couple of data sources must be collected. It is best to start with an empty folder that can be located anywhere in your file system. In the following, the folder will be denoted as `/data`. All downloaded data sets need to be put into specific sub-directories. The following paragraphs describe this process.

:::{tip} 

**Mixing code and data:** Often, when people clone the eqasim repository, they see the `data` folder and put the data sets there. This is not the intended procedure: the cloned repository only contains the processing code that should be separated from where the data is located. See [Running the pipeline](population_execution.md) for a common project directory structure.

:::

## 1) Census data (RP 2022)

Census data containing the socio-demographic information of people living in
France is available from INSEE:

- [Census data](https://www.insee.fr/fr/statistiques/8647104)
- Download the data set in **parquet** format by clicking the link under *Individus localisés au canton-ou-ville*.
- Copy the *parquet* file into the folder `data/rp_2022`

## 2) Population totals (RP 2022)

We also make use of more aggregated population totals available from INSEE:

- [Population data](https://www.insee.fr/fr/statistiques/8647014)
- Download the data for *France hors Mayotte* in **csv** format.
- Copy the *zip* file into the folder `data/rp_2022`.

## 3) Origin-destination data (RP-MOBPRO / RP-MOBSCO 2022)

Origin-destination data is available from INSEE (at two locations):

- [Work origin-destination data](https://www.insee.fr/fr/statistiques/8589904)
- [Education origin-destination data](https://www.insee.fr/fr/statistiques/8589945)
- Download the data from the links, both in **parquet** format.
- Copy both *parquet* files into the folder `data/rp_2022`.

## 4) Income tax data (Filosofi 2021)

The tax data set is available from INSEE:

- [Income tax data](https://www.insee.fr/fr/statistiques/7756855)
- Download the munipality data (first link): *Base niveau communes en 2021* in **xlsx** format
- Copy the *zip* file into the folder `data/filosofi_2021`
- Download the administrative level data (second link): *Base niveau administratif en 2021* in **xlsx** format
- Copy the second *zip* file into `data/filosofi_2021`

## 5) Service and facility census (BPE 2024)

The census of services and facilities in France is available from INSEE:

- [Service and facility census](https://www.insee.fr/fr/statistiques/8217525)
- Download the data set in **parquet** format.
- Copy the *parquet* file into the folder `data/bpe_2024`.

### 6) Departmental household travel survey (EMC2 d’Indre-et-Loire)

Usually, you do not have access to this household travel survey, which is not available publicly. 

[Download link (for researchers)](https://data.progedo.fr/series/adisp/enquetes-menages-deplacements-emd-enquetes-mobilite-certifiee-cerema-emc)

Expected format (recent Progedo exports):
`data/emc2_tours/progedo`/
├── *-Donnees_CSV  # Subdirectory names do not matter.
│   └── fichiers_standards
│       ├── *_std_depl.csv
│       ├── *_std_men.csv
│       ├── *_std_pers.csv
│       └── *_std_traj.csv
└── *-Documentation  # Subdirectory names do not matter.
    └── SIG
        ├── *_ZF(_*)?.(TAB|shp)           # Optional "Zones fines" file
        ├── *_GT(_*)?.(TAB|shp)           # Optional "Générateurs de trafic" file
        ├── *_GT_externes(_*)?.(TAB|shp)  # Optional "Générateurs de trafic" external file
        └── *_DTIR(_*)?.(TAB|shp)         # Optional "Zones de tirage" file

## 7) IRIS zoning system (2024)

The IRIS zoning system is available from IGN:

- [IRIS data](https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_CONTOURS-IRIS?redirected_from=geoservices.ign.fr)
- To download the data, follow these steps:
    1. Scroll down to the **Téléchargements et flux (6)** section.
    2. Click on **Contours...Iris**.
    3. In the **Téléchargement de données** field that appears, select the desired format: **GPKG**.
    4. Click on the year **2024** to access the *.7z* file.
- Copy the *7z* file into the folder `data/iris_2024`


## 8) Zoning registry (2023)

We make use of a zoning registry by INSEE that establishes a connection between
the identifiers of IRIS, municipalities, departments and regions:

- [Zoning data](https://www.insee.fr/fr/information/7708995)
- Download the **2024** edition as a *zip* file.
- Copy the *zip* file into `data/codes_2024`.

## 9) Enterprise census (SIRENE)

The enterprise census of France is available on data.gouv.fr:

- [Enterprise census](https://www.data.gouv.fr/fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/)
- Scroll down and click on the blue download button on the right for the two following data sets:
  - **Sirene : Fichier StockUniteLegale du dd mm yyyy (format parquet)** (where "dd mm yyyy" is the
    date), the database of enterprises
  - **Sirene : Fichier StockEtablissement du dd mm yyy (format parquet)** (where "dd mm yyyy" is the
    date), the database of enterprise facilities
- The files are updated monthly and are rather large. After downloading, you should have two files:
  - `StockEtablissement_utf8.parquet`
  - `StockUniteLegale_utf8.parquet`
- Move both *parquet* files into `data/sirene`.

The geolocated enterprise census is available on data.gouv.fr:

- [Geolocated enterprise census](https://www.data.gouv.fr/fr/datasets/geolocalisation-des-etablissements-du-repertoire-sirene-pour-les-etudes-statistiques/)
- Scroll down and click on the blue download button on the right for the following data set:
    - **Sirene : Fichier GeolocalisationEtablissement_Sirene_pour_etudes_statistiques du dd mm yyyy
      (format parquet)** (where "dd mm yyyy" is the date)
- Put the downloaded *parquet* file into `data/sirene`

## 10) Buildings database (BD TOPO)

The French Buildings database is available from IGN:

- [Buildings database](https://cartes.gouv.fr/rechercher-une-donnee/dataset/IGNF_BD-TOPO?redirected_from=geoservices.ign.fr)
- To download the data for Indre-et-Loire (D037), follow these steps:
    1. Scroll down to the **Téléchargements et flux (152)** section.
    2. Click on the arrow in the **BD TOPO® V3** field.
    3. In the **Téléchargement de données** field that appears, configure the settings as follows:
        - **ZONE**: Select `D037 - Indre-et-Loire`.
        - **Format**: Select `GPKG`.
        - **CRS**: Select `RGF93 v1 / Lambert-93`.
    4. Download the resulting file.
- Copy the file into the folder `data/bdtopo_tours`.

## 11) Adresses database (BAN)

The French adresses database is available on data.gouv.fr :

- [Adresses database](https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/)
- Click on the link *adresses-37.csv.gz*
- Copy the *gz* files into `data/ban_tours`.


## Overview

Your folder structure should now have at least the following files:

- `data/rp_2022/RP2022_indcvi.parquet`
- `data/rp_2022/RP2022_mobpro.parquet`
- `data/rp_2022/RP2022_mobsco.parquet`
- `data/rp_2022/base-ic-evol-struct-pop-2022_csv.zip`
- `data/filosofi_2021/indic-struct-distrib-revenu-2021-COMMUNES_XLSX.zip`
- `data/filosofi_2021/indic-struct-distrib-revenu-2021-SUPRA_XLSX.zip`
- `data/bpe_2024/BPE24.parquet`
- `data/emc2_tours/progedo/Csv/Fichiers_Standard/tours_2019_std_depl.csv`
- `data/emc2_tours/progedo/Csv/Fichiers_Standard/tours_2019_std_men.csv`
- `data/emc2_tours/progedo/Csv/Fichiers_Standard/tours_2019_std_pers.csv`
- `data/emc2_tours/progedo/Csv/Fichiers_Standard/tours_2019_std_traj.csv`
- `data/iris_2024/CONTOURS-IRIS_..._GPKG.7z`
- `data/codes_2024/reference_IRIS_geo2024.zip`
- `data/sirene/StockEtablissement_utf8.parquet`
- `data/sirene/StockUniteLegale_utf8.parquet`
- `data/sirene/GeolocalisationEtablissement_Sirene_pour_etudes_statistiques.parquet`
- `data/bdtopo_tours/BDTOPO_..._GPKG_D037_...7z`
- `data/ban_tours/adresses-37.csv.gz`
