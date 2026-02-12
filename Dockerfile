# Usiamo l'immagine ufficiale di Miniconda3
FROM continuumio/miniconda3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Impostazioni per QGIS Headless (senza monitor)
ENV QT_QPA_PLATFORM=offscreen
ENV XDG_RUNTIME_DIR=/tmp/runtime-root

WORKDIR /app

# 1. Copia il file environment
COPY environment.yml .

# 2. Crea l'ambiente Conda
# Questo step scaricherà tutti i binari compatibili (GDAL, QGIS, Numpy, Pandana)
RUN conda env create -f environment.yml

# 3. Imposta la shell predefinita per usare l'ambiente appena creato
# Questo è il "trucco" per far sì che ogni comando successivo (es. python ...)
# usi il python di Conda e non quello di sistema.
SHELL ["conda", "run", "-n", "city_env", "/bin/bash", "-c"]

# 4. Copia il codice sorgente
COPY . .

# 5. Configura PYTHONPATH per QGIS (Conda installa qgis in un percorso standard, 
# ma a volte serve aiutarlo a trovare i bindings python)
# Nota: Spesso con conda non serve, ma per sicurezza lo puntiamo all'env.
ENV PYTHONPATH=/opt/conda/envs/city_env/share/qgis/python

EXPOSE 5000

# 6. Avvio
# Usiamo "conda run" per assicurarci che l'ambiente sia attivo all'avvio del container
ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "city_env"]
CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]