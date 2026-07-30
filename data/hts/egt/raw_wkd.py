from tqdm import tqdm
import pandas as pd
import os

"""
This stage loads the raw data of the Île-de-France HTS (EGT).
"""

MENAGES_COLUMNS = [
    "RESDEP", "NQUEST", "POIDSM", "NB_VELO", "NB_VD", "REVENU", "RESCOMM",
    "NB_2RM", "MNP"
]

PERSONNES_COLUMNS = [
    "RESDEP", "NP", "POIDSP", "NQUEST", "SEXE", "AGE", "PERMVP",
    "ABONTC", "OCCP", "PERM2RM", "NBDEPL", "NONDEPL", "CS8"
]

DEPLACEMENTS_COLUMNS = [
    "NQUEST", "NP", "ND",
    "ORDEP", "DESTDEP", "ORH", "DESTH", "ORM", "DESTM", "ORCOMM", "DESTCOMM",
    "DPORTEE", "MODP_H7", "DESTMOT_H9", "ORMOT_H9"
]

def configure(context):
    context.config("data_path")

def execute(context):
    df_menages_sam = pd.read_csv(
        "%s/egt_2010/Menages_samedi.csv" % context.config("data_path"),
        sep = ",", encoding = "latin1", usecols = MENAGES_COLUMNS
    )

    df_menages_dim = pd.read_csv(
        "%s/egt_2010/Menages_dimanche.csv" % context.config("data_path"),
        sep = ",", encoding = "latin1", usecols = MENAGES_COLUMNS
    )

    df_personnes_sam = pd.read_csv(
        "%s/egt_2010/Personnes_samedi.csv" % context.config("data_path"),
        sep = ",", encoding = "latin1", usecols = PERSONNES_COLUMNS
    )

    df_personnes_dim = pd.read_csv(
        "%s/egt_2010/Personnes_dimanche.csv" % context.config("data_path"),
        sep = ",", encoding = "latin1", usecols = PERSONNES_COLUMNS
    )

    df_deplacements_sam = pd.read_csv(
        "%s/egt_2010/Deplacements_samedi.csv" % context.config("data_path"),
        sep = ",", encoding = "latin1", usecols = DEPLACEMENTS_COLUMNS
    )

    df_deplacements_dim = pd.read_csv(
        "%s/egt_2010/Deplacements_dimanche.csv" % context.config("data_path"),
        sep = ",", encoding = "latin1", usecols = DEPLACEMENTS_COLUMNS
    )

    return df_menages_sam, df_menages_dim, df_personnes_sam, df_personnes_dim, df_deplacements_sam, df_deplacements_dim

def validate(context):
    for name in ("Menages_samedi.csv", "Menages_dimanche.csv", "Personnes_samedi.csv", "Personnes_dimanche.csv", "Deplacements_samedi.csv", "Deplacements_dimanche.csv"):
        if not os.path.exists("%s/egt_2010/%s" % (context.config("data_path"), name)):
            raise RuntimeError("File missing from EGT: %s" % name)

    return [
        os.path.getsize("%s/egt_2010/Menages_samedi.csv" % context.config("data_path")),
        os.path.getsize("%s/egt_2010/Menages_dimanche.csv" % context.config("data_path")),
        os.path.getsize("%s/egt_2010/Personnes_samedi.csv" % context.config("data_path")),
        os.path.getsize("%s/egt_2010/Personnes_dimanche.csv" % context.config("data_path")),
        os.path.getsize("%s/egt_2010/Deplacements_samedi.csv" % context.config("data_path")),
        os.path.getsize("%s/egt_2010/Deplacements_samedi.csv" % context.config("data_path"))
    ]
