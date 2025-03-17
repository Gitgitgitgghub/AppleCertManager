# log_config.py
import logging
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

def configure_logging():
    # 配置 root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    custom_theme = Theme({
        "debug": "cyan",
        "info": "green",
        "warning": "yellow",
        "error": "red",
        "critical": "bold red"
    })
    
    console = Console(theme=custom_theme)
    
    class ColoredRichHandler(RichHandler):
        def emit(self, record):
            level_name = record.levelname.lower()
            message = self.format(record)
            self.console.print(f"[{level_name}]{message}[/{level_name}]")
    
    class CustomFormatter(logging.Formatter):
        def format(self, record):
            levelname = record.levelname
            name = record.name
            message = record.getMessage()
            return f"{levelname}:{name}:{message}"
    
    handler = ColoredRichHandler(console=console, show_time=False, show_path=False, show_level=False)
    handler.setFormatter(CustomFormatter())
    
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    return root_logger