# Spark relationship notebooks

The seven themed notebooks use the same 17 selected study fields. Pick a focus variable
from the notebook's theme and compare it with the other 16 using Spark. Each provides
ranked Pearson correlations, valid pair counts, and a selectable Altair scatterplot
grid with pooled regression lines, coverage checks, and CSV exports. Choose up to 12
comparison variables before rendering the grid and set two to four grid columns.
Each notebook also includes a 17-panel elevation grid based on Spark-computed
location means, with shared elevation axes and independently scaled measurements.
The time-series grid supports weekly, monthly, and yearly views for the current focus
and scatter-grid selections, with separate lines for each elevation band.

| `RELATIONSHIP` value | Focus group |
| --- | --- |
| `thermal` | Air, apparent, dew-point and shallow-soil temperatures |
| `hydrology` | Humidity, precipitation, rain, evapotranspiration and vapour-pressure deficit |
| `wind` | 100 m wind speed |
| `clouds_weather` | Total cloud cover |
| `pressure_boundary` | Sea-level/surface pressure and boundary-layer height |
| `soil_moisture` | Shallow (0–7 cm) soil moisture |
| `radiation` | Sunshine duration and direct radiation |

From the project root:

```bash
make notebook-relationships RELATIONSHIP=thermal
make notebook-relationships RELATIONSHIP=wind
```

The default is `thermal`. The notebooks automatically prefer a published release;
before publication they can explore downloaded raw Parquet partitions and clearly
label the result as incomplete.
