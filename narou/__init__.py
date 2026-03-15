import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("narou.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
