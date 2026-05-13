FROM docker.io/condaforge/miniforge3:23.11.0-0

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# SOLO conda-forge, niente defaults
RUN printf "%s\n" \
  "channels:" \
  "  - conda-forge" \
  "channel_priority: strict" \
  > /opt/conda/.condarc

# Crea env CONDA con TUTTO lo stack GIS + Flask
RUN mamba create -n geo_indicators -y \
      python=3.9 \
      gdal \
      flask \
      pandas \
      geopandas \
      scipy \
      "numpy<2" \
      pydantic=1.10 \
      typing_extensions \
      ujson \
      soupsieve \
      geojson \
      pandana \
      osmnet \
      osmnx \
      rtree \
      pyproj \
      shapely \
      requests \
      beautifulsoup4 \
      osmpythontools \
      boto3 \
      botocore \
      s3transfer && \
    conda clean -afy

ENV CONDA_DEFAULT_ENV=geo_indicators
ENV PATH=/opt/conda/envs/geo_indicators/bin:$PATH
WORKDIR /app

# pip SOLO per extra non conda ✅
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia app
COPY . .

EXPOSE 5000

# Avvio API (dentro env conda)

ENV CONDA_DEFAULT_ENV=geo_indicators
ENV PATH=/opt/conda/envs/geo_indicators/bin:$PATH
ENV PYTHONUNBUFFERED=1

CMD ["/opt/conda/envs/geo_indicators/bin/python", "main_15min_api.py"]
