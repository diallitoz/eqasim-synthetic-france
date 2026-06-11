# Gathering additional data

In this section we refere to the same data directory structure as described when
gathering the data for the [synthetic population](../population/population_summary.md).

## I) Road network (OpenStreetMap)

The road network in the pipeline is based on OpenStreetMap data.
A cut-out for Centre-Val de Loire is available from Geofabrik:

- [Centre-Val de Loire OSM](https://download.geofabrik.de/europe/france/centre.html)
- Download *centre-latest.osm.pbf* and put it into the folder `data/osm_centre_val_loire`.

## II) Public transit schedule (GTFS)

- **Réseau urbain et périurbain Fil Bleu**
    - Go to [Transport Data Gouv](https://transport.data.gouv.fr/datasets/fil-bleu-syndicat-des-mobilites-gtfs-gtfs-rt)
    - Under *Données statiques*, click on **Télécharger**.
    - Put the downloaded file into the folder `data/gtfs_tours` and rename it to `fil_bleu.zip`.

- **Réseau interurbain Rémi** 
    - Go to [Transport Data Gouv](https://transport.data.gouv.fr/datasets/remi-offre-theorique-mobilite-reseau-interurbain-regional)
    - Under *Données statiques* > *REMI GTFS*, click on **Télécharger**.
    - Put the downloaded file into the folder `data/gtfs_tours` and rename it to `remi.zip`.

Note that this schedule is updated regularly and is only valid for the next three
weeks.

## Overview

In your directory structure, there should now be the following additional files:

- `data/osm_centre_val_loire/centre-260608.osm.pbf`
- `data/gtfs_tours/fil_bleu.zip`
- `data/gtfs_tours/REMI.zip`
