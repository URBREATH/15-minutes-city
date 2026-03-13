import logging
from logging.handlers import RotatingFileHandler
import os

# === Percorso del log ===
LOG_PATH = "/home/script-3-30-300/script_work_chiara/city15_simulation/15min_logger.log"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

# === Logger globale ===
logger = logging.getLogger("15min_logger")
logger.setLevel(logging.INFO)

# Evita di aggiungere più handler se il modulo viene importato più volte
if not logger.handlers:

    # === Rotating file handler ===
    handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10 * 1024 * 1024,  # 10 MB per file
        backupCount=3               # mantiene 3 backup
    )

    # === Formatter ===
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    # === Aggiunge handler al logger ===
    logger.addHandler(handler)