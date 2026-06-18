# config.py
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class LogConfig:
    """Конфигурация для чтения логов"""
    # Путь к папке с логами (обязательный параметр)
    log_directory: str
    
    # Паттерны для поиска файлов
    master_pattern: str = "gpdb-*-master*.csv"
    segment_pattern: str = "gpdb-*-seg*.csv"
    alternative_master: str = "postgresql-*.csv"
    
    # Настройки фильтрации
    min_severity: str = "ERROR"  # DEBUG, LOG, NOTICE, WARNING, ERROR, FATAL, PANIC
    time_from: Optional[str] = None  # "2024-01-15 14:00:00"
    time_to: Optional[str] = None    # "2024-01-15 15:00:00"
    
    # Настройки обработки
    max_file_size_gb: float = 10.0
    chunk_size_mb: int = 100  # Размер чанка для потокового чтения
    
    def validate(self) -> bool:
        """Проверка существования директории"""
        path = Path(self.log_directory)
        if not path.exists():
            raise ValueError(f"Директория не существует: {self.log_directory}")
        if not path.is_dir():
            raise ValueError(f"Указанный путь не является директорией: {self.log_directory}")
        return True