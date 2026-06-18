# main.py - Обновленная версия с фильтрацией
import re
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter


class LogParser:
    """Parser for Greenplum CSV logs"""
    
    def __init__(self, time_from: datetime = None, time_to: datetime = None):
        self.time_from = time_from
        self.time_to = time_to
        self.ERROR_PATTERNS = {
            'OUT_OF_MEMORY': [
                (r'out of memory', 'oom'),
                (r'work_mem exceeded', 'work_mem'),
                (r'gp_vmem_protect_limit', 'vmem_limit'),
                (r'Virtual Memory', 'virtual_memory'),
                (r'Memory exhausted', 'memory_exhausted'),
            ],
            'QUERY_ERROR': [
                (r'relation.*does not exist', 'relation_missing'),
                (r'missing FROM-clause', 'syntax_error'),
                (r'syntax error', 'syntax_error'),
                (r'column.*does not exist', 'column_missing'),
                (r'function.*does not exist', 'function_missing'),
                (r'schema.*does not exist', 'schema_missing'),
            ],
            'DUPLICATE_KEY': [
                (r'duplicate key', 'duplicate_key'),
                (r'violates unique constraint', 'constraint_violation'),
            ],
            'DATA_ERROR': [
                (r'invalid input syntax', 'invalid_input'),
                (r'data format error', 'format_error'),
                (r'skipping external table row', 'external_table'),
                (r'value too long', 'value_too_long'),
            ],
            'PANIC': [
                (r'PANIC', 'system_panic'),
                (r'Unexpected internal error', 'internal_error'),
                (r'shared memory corruption', 'shared_memory'),
            ],
            'SIGNAL_ERROR': [
                (r'SIGSEGV', 'sigsegv'),
                (r'SIGBUS', 'sigbus'),
                (r'received signal', 'signal'),
            ],
            'INTERCONNECT_ERROR': [
                (r'interconnect', 'interconnect'),
                (r'Connection refused', 'connection_refused'),
                (r'failed to connect', 'connection_failed'),
                (r'broken pipe', 'broken_pipe'),
                (r'Connection reset', 'connection_reset'),
            ],
            'DEADLOCK': [
                (r'deadlock detected', 'deadlock'),
                (r'deadlock', 'deadlock_simple'),
            ],
            'DISK_ERROR': [
                (r'disk full', 'disk_full'),
                (r'no space left', 'no_space'),
                (r'could not write', 'write_error'),
                (r'I/O error', 'io_error'),
            ],
            'CONNECTION_ERROR': [
                (r'too many clients', 'too_many_clients'),
                (r'authentication failed', 'auth_failed'),
                (r'connection limit exceeded', 'connection_limit'),
            ],
        }
    
    def parse_line(self, line: str) -> dict:
        """Parse one CSV line, return dict if error/warning found"""
        line = line.strip()
        if not line:
            return None
        
        if line.startswith('event_time'):
            return None
        
        try:
            parts = line.split(',')
            
            if len(parts) < 16:
                return None
            
            severity = parts[13].strip().upper() if len(parts) > 13 else ''
            
            if severity not in ['ERROR', 'FATAL', 'PANIC', 'WARNING']:
                return None
            
            # Парсим время
            ts_str = parts[0].strip()
            timestamp = self._parse_timestamp(ts_str)
            
            # Фильтрация по времени
            if self.time_from and timestamp < self.time_from:
                return None
            if self.time_to and timestamp > self.time_to:
                return None
            
            message = parts[15].strip() if len(parts) > 15 else ''
            detail = parts[16].strip() if len(parts) > 16 and parts[16].strip() else ''
            hint = parts[17].strip() if len(parts) > 17 and parts[17].strip() else ''
            query = parts[21].strip() if len(parts) > 21 and parts[21].strip() else ''
            
            error_type, error_subtype = self._classify(message, detail, hint)
            
            return {
                'timestamp': timestamp,
                'user': parts[1].strip() if len(parts) > 1 else '',
                'database': parts[2].strip() if len(parts) > 2 else '',
                'host': parts[5].strip() if len(parts) > 5 else '',
                'segment': parts[11].strip() if len(parts) > 11 else '',
                'severity': severity,
                'sql_state': parts[14].strip() if len(parts) > 14 else '',
                'message': message,
                'detail': detail,
                'hint': hint,
                'query': query,
                'error_type': error_type or 'UNKNOWN',
                'error_subtype': error_subtype or 'unclassified',
                'source_file': getattr(self, 'current_file', 'unknown'),
            }
        except:
            return None
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        formats = [
            '%Y-%m-%d %H%M%S.%f %Z',
            '%Y-%m-%d %H%M%S.%f',
            '%Y-%m-%d %H:%M:%S.%f %Z',
            '%Y-%m-%d %H:%M:%S.%f',
        ]
        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except:
                continue
        return datetime.now()
    
    def _classify(self, message: str, detail: str, hint: str) -> tuple:
        text = f"{message} {detail} {hint}"
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern, subtype in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return error_type, subtype
        return 'OTHER_ERROR', 'unclassified'


def read_file_lines(filepath: Path) -> list:
    """Read lines from file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.readlines()
    except:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                return f.readlines()
        except:
            return []


def find_log_files(path: Path) -> list:
    """Find all log files in directory or single file"""
    if path.is_file():
        return [path]
    
    log_files = []
    patterns = ['*.csv', '*.log', '*.csv.gz', '*.log.gz']
    
    for pattern in patterns:
        log_files.extend(path.glob(pattern))
    
    # Сортировка по имени файла
    log_files.sort(key=lambda f: f.name)
    
    return log_files


def print_summary(entries: list):
    """Print summary before AI analysis"""
    if not entries:
        print("\n" + "=" * 70)
        print(" No errors found in specified time range")
        print("=" * 70)
        return
    
    severity_count = Counter(e['severity'] for e in entries)
    type_count = Counter(e['error_type'] for e in entries)
    files = set(e.get('source_file', '') for e in entries)
    
    print(f"\n{'─' * 70}")
    print(" QUICK SUMMARY")
    print(f"{'─' * 70}")
    print(f"  Files processed: {len(files)}")
    print(f"  Total errors/warnings: {len(entries)}")
    print(f"  Time range: {min(e['timestamp'] for e in entries).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"            → {max(e['timestamp'] for e in entries).strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n  Severity:")
    for sev in ['PANIC', 'FATAL', 'ERROR', 'WARNING']:
        count = severity_count.get(sev, 0)
        if count > 0:
            print(f"    {sev}: {count}")
    
    print(f"\n  Error types:")
    for etype, count in type_count.most_common(5):
        print(f"    {etype}: {count}")


def main():
    import argparse
    
    parser_arg = argparse.ArgumentParser(
        description='Greenplum Log Analyzer with time filtering',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py logs/
  python main.py logs/ --from "2026-06-18 14:00:00" --to "2026-06-18 15:00:00"
  python main.py logs/ --from "2026-06-18 14:30:00"
  python main.py logs/ --last 2h
  python main.py logs/ --last 30m
        """
    )
    
    parser_arg.add_argument('path', type=str, help='Path to log file or directory')
    
    parser_arg.add_argument(
        '--from', dest='time_from', type=str, default=None,
        help='Start time (format: "YYYY-MM-DD HH:MM:SS")'
    )
    
    parser_arg.add_argument(
        '--to', dest='time_to', type=str, default=None,
        help='End time (format: "YYYY-MM-DD HH:MM:SS")'
    )
    
    parser_arg.add_argument(
        '--last', type=str, default=None,
        help='Analyze last N period (e.g., "2h", "30m", "1d")'
    )
    
    parser_arg.add_argument(
        '-o', '--output', type=str, default='parsed_errors.json',
        help='Output file for parsed errors (default: parsed_errors.json)'
    )
    
    args = parser_arg.parse_args()
    
    # Парсим время
    time_from = None
    time_to = None
    
    if args.time_from:
        try:
            time_from = datetime.strptime(args.time_from, '%Y-%m-%d %H:%M:%S')
        except:
            print(f"[ERROR] Invalid time format: {args.time_from}")
            print("        Use: YYYY-MM-DD HH:MM:SS")
            sys.exit(1)
    
    if args.time_to:
        try:
            time_to = datetime.strptime(args.time_to, '%Y-%m-%d %H:%M:%S')
        except:
            print(f"[ERROR] Invalid time format: {args.time_to}")
            sys.exit(1)
    
    if args.last:
        import re
        match = re.match(r'(\d+)([hmd])', args.last.lower())
        if match:
            value = int(match.group(1))
            unit = match.group(2)
            
            now = datetime.now()
            if unit == 'h':
                time_from = now - timedelta(hours=value)
            elif unit == 'm':
                time_from = now - timedelta(minutes=value)
            elif unit == 'd':
                time_from = now - timedelta(days=value)
            
            print(f"[INFO] Filtering from: {time_from.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"[ERROR] Invalid --last format. Use: 2h, 30m, 1d")
            sys.exit(1)
    
    input_path = Path(args.path)
    
    if not input_path.exists():
        print(f"[ERROR] Path not found: {input_path}")
        sys.exit(1)
    
    print("=" * 70)
    print(" GREENPLUM LOG PARSER")
    print("=" * 70)
    print(f"Path: {input_path}")
    
    if time_from:
        print(f"From: {time_from.strftime('%Y-%m-%d %H:%M:%S')}")
    if time_to:
        print(f"To:   {time_to.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Поиск файлов
    print(f"\n[INFO] Searching for log files...")
    log_files = find_log_files(input_path)
    
    if not log_files:
        print(f"[ERROR] No .csv or .log files found")
        sys.exit(1)
    
    print(f"[INFO] Found {len(log_files)} file(s):")
    total_size = 0
    for f in log_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        total_size += size_mb
        print(f"  - {f.name} ({size_mb:.1f} MB)")
    print(f"  Total size: {total_size:.1f} MB")
    
    # Парсинг всех файлов
    parser = LogParser(time_from=time_from, time_to=time_to)
    all_entries = []
    total_lines = 0
    
    for filepath in log_files:
        print(f"\n[INFO] Processing: {filepath.name}...")
        parser.current_file = filepath.name
        
        lines = read_file_lines(filepath)
        total_lines += len(lines)
        
        file_entries = []
        for line in lines:
            entry = parser.parse_line(line)
            if entry:
                file_entries.append(entry)
        
        all_entries.extend(file_entries)
        
        filtered = len(file_entries)
        print(f"  Lines: {len(lines)}, Errors found: {filtered}")
    
    print(f"\n[INFO] Total lines processed: {total_lines}")
    print(f"[INFO] Total errors extracted: {len(all_entries)}")
    
    # Сохраняем результат
    import json
    output_data = {
        'parse_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_errors': len(all_entries),
        'time_filter': {
            'from': time_from.strftime('%Y-%m-%d %H:%M:%S') if time_from else None,
            'to': time_to.strftime('%Y-%m-%d %H:%M:%S') if time_to else None,
        },
        'files_processed': [f.name for f in log_files],
        'errors': [
            {
                'timestamp': e['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'severity': e['severity'],
                'error_type': e['error_type'],
                'message': e['message'],
                'detail': e.get('detail', ''),
                'host': e.get('host', ''),
                'segment': e.get('segment', ''),
                'database': e.get('database', ''),
                'query': e.get('query', ''),
                'source_file': e.get('source_file', ''),
            }
            for e in all_entries
        ]
    }
    
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"[INFO] Parsed errors saved to: {args.output}")
    
    # Вывод сводки
    print_summary(all_entries)
    
    return all_entries, output_data


if __name__ == '__main__':
    main()