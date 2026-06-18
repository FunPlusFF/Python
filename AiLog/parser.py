# Сохраните как gp_analyzer_v2.py в C:\Users\FunPlus\Documents\AiLog

import re
import os
import sys
import gzip
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter


class LogParser:
    """Parser for Greenplum CSV logs (custom 28-column format)"""
    
    def __init__(self):
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
                (r'violates foreign key constraint', 'fk_violation'),
            ],
            'DATA_ERROR': [
                (r'invalid input syntax', 'invalid_input'),
                (r'data format error', 'format_error'),
                (r'skipping external table row', 'external_table'),
                (r'value too long', 'value_too_long'),
                (r'numeric field overflow', 'numeric_overflow'),
            ],
            'PANIC': [
                (r'PANIC', 'system_panic'),
                (r'Unexpected internal error', 'internal_error'),
                (r'segment process failed', 'segment_failed'),
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
                (r'waits for.*Lock', 'lock_wait'),
            ],
            'DISK_ERROR': [
                (r'disk full', 'disk_full'),
                (r'no space left', 'no_space'),
                (r'could not write', 'write_error'),
                (r'could not read', 'read_error'),
                (r'I/O error', 'io_error'),
            ],
            'CONNECTION_ERROR': [
                (r'too many clients', 'too_many_clients'),
                (r'authentication failed', 'auth_failed'),
                (r'connection limit exceeded', 'connection_limit'),
                (r'connection refused', 'connection_refused'),
            ],
        }
    
    def parse_line(self, line: str) -> dict:
        """Parse one CSV line, return dict if it contains error/warning"""
        line = line.strip()
        if not line:
            return None
        
        # Skip header
        if line.startswith('event_time'):
            return None
        
        try:
            parts = line.split(',')
            
            # Need at least 16 fields
            if len(parts) < 16:
                return None
            
            severity = parts[13].strip().upper() if len(parts) > 13 else ''
            
            # Only process errors, fatals, panics, warnings
            if severity not in ['ERROR', 'FATAL', 'PANIC', 'WARNING']:
                return None
            
            # Parse timestamp
            ts_str = parts[0].strip()
            timestamp = self._parse_timestamp(ts_str)
            
            message = parts[15].strip() if len(parts) > 15 else ''
            detail = parts[16].strip() if len(parts) > 16 and parts[16].strip() else ''
            hint = parts[17].strip() if len(parts) > 17 and parts[17].strip() else ''
            query = parts[21].strip() if len(parts) > 21 and parts[21].strip() else ''
            
            # Classify error
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
            }
        except:
            return None
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse timestamp string to datetime"""
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
        """Classify error by matching patterns"""
        text = f"{message} {detail} {hint}"
        
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern, subtype in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return error_type, subtype
        
        return 'OTHER_ERROR', 'unclassified'


def analyze_file(filepath: Path):
    """Analyze a single log file"""
    print(f"\n{'=' * 70}")
    print(f" ANALYZING: {filepath.name}")
    print(f"{'=' * 70}")
    
    # Read file
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except:
        with open(filepath, 'r', encoding='latin-1') as f:
            lines = f.readlines()
    
    print(f"Total lines: {len(lines)}")
    
    # Parse
    parser = LogParser()
    entries = []
    
    for line in lines:
        entry = parser.parse_line(line)
        if entry:
            entries.append(entry)
    
    print(f"Errors/Warnings found: {len(entries)}")
    
    if not entries:
        print("\nNo errors found!")
        return
    
    # Statistics
    severity_count = Counter(e['severity'] for e in entries)
    type_count = Counter(e['error_type'] for e in entries)
    host_count = Counter(e['host'] for e in entries if e['host'])
    
    print(f"\n{'─' * 70}")
    print(" SEVERITY BREAKDOWN")
    print(f"{'─' * 70}")
    for sev in ['PANIC', 'FATAL', 'ERROR', 'WARNING']:
        count = severity_count.get(sev, 0)
        if count > 0:
            bar = '█' * min(count, 50)
            print(f"  {sev:10s}: {count:3d}  {bar}")
    
    print(f"\n{'─' * 70}")
    print(" ERROR TYPES")
    print(f"{'─' * 70}")
    for etype, count in type_count.most_common():
        print(f"  {etype:25s}: {count:3d}")
    
    print(f"\n{'─' * 70}")
    print(" SAMPLE ERRORS")
    print(f"{'─' * 70}")
    
    # Show one example of each type
    shown_types = set()
    for entry in entries:
        if entry['error_type'] not in shown_types:
            shown_types.add(entry['error_type'])
            print(f"\n  [{entry['severity']}] [{entry['error_type']}]")
            print(f"  Time    : {entry['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Host    : {entry['host']}, DB: {entry['database']}")
            print(f"  Message : {entry['message'][:120]}")
            if entry['detail']:
                print(f"  Detail  : {entry['detail'][:120]}")
            if entry['query']:
                print(f"  Query   : {entry['query'][:120]}")
    
    print(f"\n{'─' * 70}")
    print(" TOP 5 MOST FREQUENT MESSAGES")
    print(f"{'─' * 70}")
    
    msg_count = Counter(e['message'][:100] for e in entries)
    for i, (msg, count) in enumerate(msg_count.most_common(5), 1):
        print(f"  {i}. [{count}x] {msg}")
    
    print(f"\n{'=' * 70}")
    print(" ANALYSIS COMPLETE")
    print(f"{'=' * 70}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python gp_analyzer_v2.py <file_or_directory>")
        print("Examples:")
        print("  python gp_analyzer_v2.py err/test_greenplum_log.csv")
        print("  python gp_analyzer_v2.py err/")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"[ERROR] Path not found: {input_path}")
        sys.exit(1)
    
    print("=" * 70)
    print(" GREENPLUM LOG ANALYZER v2")
    print("=" * 70)
    print(f"Path: {input_path}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if input_path.is_file():
        analyze_file(input_path)
    else:
        # Process all CSV files in directory
        log_files = list(input_path.glob('*.csv')) + list(input_path.glob('*.log'))
        
        if not log_files:
            print(f"[ERROR] No .csv or .log files found in {input_path}")
            sys.exit(1)
        
        print(f"\n[INFO] Found {len(log_files)} file(s)")
        
        for filepath in log_files:
            analyze_file(filepath)


if __name__ == '__main__':
    main()