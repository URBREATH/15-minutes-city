
# Base image
FROM docker.io/continuumio/miniconda3:latest

# (Opzionale) pacchetti utili
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Crea env e installa TUTTO con conda-forge (evita pip che compila numpy/scipy)

RUN conda update -n base -c defaults conda -y && \
    conda install -n base -c conda-forge mamba -y && \
    conda config --set channel_priority strict && \
    mamba create -n geo_indicators -y -c conda-forge \
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
      botocore && \
    conda clean -afy


# Rende l'env "attivo" per i RUN successivi senza usare SHELL (Podman OCI friendly)
ENV CONDA_DEFAULT_ENV=geo_indicators
ENV PATH=/opt/conda/envs/geo_indicators/bin:$PATH

WORKDIR /app

# Se vuoi tenere requirements.txt, installa SOLO eventuali pacchetti extra
# (e NON far reinstallare dipendenze già messe da conda)
COPY requirements.txt .
RUN pip install --no-cache-dir --no-deps -r requirements.txt || true

# Copia app
COPY . .

EXPOSE 5000

# Avvio API (dentro env conda)

ENV CONDA_DEFAULT_ENV=geo_indicators
ENV PATH=/opt/conda/envs/geo_indicators/bin:$PATH
ENV PYTHONUNBUFFERED=1

CMD ["/opt/conda/envs/geo_indicators/bin/python", "main_15min_api.py"]
