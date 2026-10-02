# Village Inventory

`villages_mh.csv` is a filtered derivative of DataMeet's Maharashtra Indian Village Boundaries database. It uses Census 2011 village names joined by `CEN_2001` to the source's Census 2001 district/subdistrict names. Taluka aliases are normalized to the spellings used by this application. Village centroids are calculated from the source boundary polygons and used as approximate spatial model features; they are not verified dumping-site coordinates.

Source: [DataMeet Indian Village Boundaries](https://github.com/datameet/indian_village_boundaries)  
Project notes: [Indian Village Boundaries](https://projects.datameet.org/indian_village_boundaries/)  
License: [Open Data Commons Open Database License 1.0](https://opendatacommons.org/licenses/odbl/)

Attribution: Village hierarchy data is derived from the DataMeet Indian Village Boundaries project and is available under ODbL. The source notes that its administrative names are Census 2001 vintage and that the data may contain errors. It is an inventory for selection, not verified incident or risk data.

To rebuild the CSV, download `mh2.geojson` and `mh.csv` from the source repository and run:

```powershell
py data/build_village_inventory.py C:\path\to\mh2.geojson C:\path\to\mh.csv
```