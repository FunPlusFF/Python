# log_reader.py
import os
import gzip
from pathlib import Path
from typing import List, Iterator, Tuple, Optional
from datetime import datetime
import fnmatch

class LogReader:
    """Чтение логов Greenplum из указанной папки"""
    
    def __init__(self, config):
        self.config = config
        self.config.validate()
        self.log_dir = Path(config.log_directory)
        
    def find_log_files(self) -> dict:
        """
        Поиск всех лог-файлов в указанной директории.
        Возвращает словарь с категориями файлов.
        """
        result = {
            'master': [],
            'segments': [],
            'other': []
        }
        
        print(f"[INFO] Поиск логов в директории: {self.log_dir.absolute()}")
        
        # Рекурсивный обход всех файлов
        all_files = []
        for root, dirs, files in os.walk(self.log_dir):
            for file in files:
                if file.endswith(('.csv', '.csv.gz', '.log', '.log.gz')):
                    full_path = Path(root) / file
                    all_files.append(full_path)
        
        if not all_files:
            print(f"[WARNING] Лог-файлы не найдены в {self.log_dir}")
            return result
        
        print(f"[INFO] Найдено файлов: {len(all_files)}")
        
        # Классификация файлов
        for filepath in all_files:
            filename = filepath.name
            
            # Проверяем паттерны мастера
            if (fnmatch.fnmatch(filename, self.config.master_pattern) or
                fnmatch.fnmatch(filename, self.config.alternative_master)):
                result['master'].append(filepath)
                print(f"[INFO] Master лог: {filepath.name}")
            
            # Проверяем паттерны сегментов
            elif fnmatch.fnmatch(filename, self.config.segment_pattern):
                result['segments'].append(filepath)
                print(f"[INFO] Segment лог: {filepath.name}")
            
            # Остальные CSV файлы
            else:
                result['other'].append(filepath)
                print(f"[INFO] Другой лог: {filepath.name}")
        
        return result
    
    def read_file_lines(self, filepath: Path, time_from: Optional[datetime] = None,
                       time_to: Optional[datetime] = None) -> Iterator[str]:
        """
        Построчное чтение файла с поддержкой gzip.
        Возвращает итератор строк.
        """
        # Проверка размера файла
        file_size_gb = filepath.stat().st_size / (1024**3)
        if file_size_gb > self.config.max_file_size_gb:
            print(f"[WARNING] Файл {filepath.name} слишком большой ({file_size_gb:.2f} GB). "
                  f"Может потребоваться много времени.")
        
        # Выбор способа открытия
        if filepath.suffix == '.gz':
            file_handle = gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore')
        else:
            file_handle = open(filepath, 'r', encoding='utf-8', errors='ignore')
        
        line_count = 0
        error_count = 0
        
        try:
            for line in file_handle:
                line_count += 1
                
                # Фильтрация по severity (быстрая проверка без парсинга)
                if not self._quick_severity_check(line):
                    continue
                
                error_count += 1
                yield line
                
                # Прогресс каждые 100000 строк
                if line_count % 100000 == 0:
                    print(f"  [PROGRESS] {filepath.name}: обработано {line_count} строк, "
                          f"найдено ошибок: {error_count}")
        
        finally:
            file_handle.close()
            print(f"  [DONE] {filepath.name}: всего строк {line_count}, ошибок {error_count}")
    
    def _quick_severity_check(self, line: str) -> bool:
        """
        Быстрая проверка строки на минимальный уровень severity.
        Позволяет отфильтровать DEBUG/LOG строки без полного парсинга.
        """
        min_sev = self.config.min_severity.upper()
        
        # Если нужно все строки - возвращаем True
        if min_sev == 'DEBUG':
            return True
        
        # Иерархия severity
        severity_levels = {
            'DEBUG': 0,
            'LOG': 1,
            'NOTICE': 2,
            'WARNING': 3,
            'ERROR': 4,
            'FATAL': 5,
            'PANIC': 6
        }
        
        min_level = severity_levels.get(min_sev, 4)  # По умолчанию ERROR
        
        # Быстрый поиск ключевых слов в строке
        for sev, level in severity_levels.items():
            if level >= min_level and sev in line.upper():
                return True
        
        return False
    
    def read_all_logs(self) -> Iterator[Tuple[str, Path, str]]:
        """
        Чтение всех найденных логов.
        Возвращает итератор кортежей: (категория, путь_к_файлу, строка_лога)
        """
        files = self.find_log_files()
        
        # Сначала читаем мастер
        for filepath in files['master']:
            print(f"\n[INFO] Чтение master лога: {filepath.name}")
            for line in self.read_file_lines(filepath):
                yield ('master', filepath, line)
        
        # Затем сегменты
        for filepath in files['segments']:
            print(f"\n[INFO] Чтение segment лога: {filepath.name}")
            for line in self.read_file_lines(filepath):
                yield ('segment', filepath, line)
        
        # Затем остальные файлы
        for filepath in files['other']:
            print(f"\n[INFO] Чтение дополнительного лога: {filepath.name}")
            for line in self.read_file_lines(filepath):
                yield ('other', filepath, line)