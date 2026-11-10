
import logging
from pathlib import Path


# ==========================================
# 1. CREATE LOG DIRECTORY
# ==========================================

LOG_DIRECTORY = Path("logs")
LOG_DIRECTORY.mkdir(exist_ok=True)


# ==========================================
# 2. CONFIGURE LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_DIRECTORY / "application.log",
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)


# ==========================================
# 3. CREATE LOGGER
# ==========================================

logger = logging.getLogger("IT_SUPPORT_SYSTEM")


# ==========================================
# 4. ERROR HANDLER
# ==========================================

def handle_error(error, context="General"):

    logger.exception(
        "Error occurred in %s: %s",
        context,
        error
    )

    return {
        "success": False,
        "error": str(error),
        "context": context
    }


# ==========================================
# 5. INFORMATION LOGGER
# ==========================================

def log_info(message):
    logger.info(message)


# ==========================================
# 6. WARNING LOGGER
# ==========================================

def log_warning(message):
    logger.warning(message)


# ==========================================
# 7. ERROR LOGGER
# ==========================================

def log_error(message):
    logger.error(message)
