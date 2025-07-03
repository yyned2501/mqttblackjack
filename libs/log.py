import logging
from logging.handlers import RotatingFileHandler

formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s - %(filename)s:%(lineno)d - %(message)s"
)

logger = logging.getLogger("main")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


play_logger = logging.getLogger("play")
play_log_file = "logs/play.log"
play_logger.setLevel(logging.INFO)
file_handler = RotatingFileHandler(play_log_file, maxBytes=10 * 1024 * 1024, backupCount=10, encoding="utf-8")
file_handler.setFormatter(formatter)
play_logger.addHandler(file_handler)    
play_logger.addHandler(console_handler)    