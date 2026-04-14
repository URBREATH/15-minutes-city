# Base image
FROM continuumio/miniconda3

# Install git
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Create the conda environment with python and qgis
RUN conda create -n geo_indicators python=3.9 qgis gdal -c conda-forge -y

# Set the shell to run within the conda environment
SHELL ["conda", "run", "-n", "geo_indicators", "/bin/bash", "-c"]

# Set working directory
WORKDIR /app

# Copy and install requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port and run the application
EXPOSE 5000
CMD ["conda", "run", "-n", "geo_indicators", "python", "main_15min_api.py"]
