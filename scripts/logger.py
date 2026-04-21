import logging
from logging.handlers import RotatingFileHandler
import os

# === Percorso del log ===
BASE_DIR = os.getcwd() 
LOG_PATH = os.path.join(BASE_DIR, "log", "15min_logger.log")
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

    # “manda i log nella console” (stdout)
    # usa lo stesso formato dei log del file (timestamp, livello, messaggio)
    # collega questo comportamento al  logger

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
