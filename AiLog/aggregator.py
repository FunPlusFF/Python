# gp_analyzer.py - All-in-one Greenplum Log Analyzer
import re
import os
import sys
import gzip
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class ParsedLogEntry:
    """Parsed Greenplum log entry"""
    timestamp: datetime
    user: str
    database: str
    pid: int
    host: str
    segment: str
    severity: str
    sql_state: str
    message: str
    detail: Optional[str]
    hint: Optional[str]
    query: Optional[str]
    raw_line: str
    category: str
    error_type: Optional[str] = None
    error_subtype: Optional[str] = None


class LogParser:
    """Parser for Greenplum CSV logs"""
    
    CSV_PATTERN = re.compile(
        r'^(?P<timestamp>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\.\d+\s+\w+),'
        r'"(?P<user>[^"]*)",'
        r'"(?P<database>[^"]*)",'
        r'(?P<pid>\d+),'
        r'"(?P<thread>[^"]*)",'
        r'"(?P<host>[^"]*)",'
        r'"(?P<session>[^"]*)",'
        r'(?P<cmd_num>\d+),'
        r'"(?P<segment>[^"]*)",'
        r'(?P<slice>\d*),'
        r'"(?P<severity>[^"]*)",'
        r'"(?P<sql_state>[^"]*)",'
        r'"(?P<message>[^"]*)",'
        r'"(?P<detail>[^"]*)",'
        r'"(?P<hint>[^"]*)",'
        r'(?P<query>.*)'
    )
    
    ERROR_PATTERNS = {
        'PANIC': [
            (r'PANIC', 'system_panic'),
            (r'Unexpected internal error', 'internal_error'),
        ],
        'OUT_OF_MEMORY': [
            (r'out of memory', 'oom'),
            (r'Out of memory', 'oom'),
            (r'gp_vmem_protect_limit', 'vmem_limit'),
            (r'Virtual Memory', 'virtual_memory'),
        ],
        'INTERCONNECT_ERROR': [
            (r'interconnect', 'interconnect'),
            (r'Connection refused', 'connection_refused'),
            (r'failed to connect', 'connection_failed'),
            (r'timeout', 'timeout'),
            (r'broken pipe', 'broken_pipe'),
        ],
        'SIGNAL_ERROR': [
            (r'SIGSEGV', 'sigsegv'),
            (r'SIGBUS', 'sigbus'),
            (r'segmentation fault', 'segfault'),
            (r'was terminated by signal', 'signal_terminated'),
        ],
        'DEADLOCK': [
            (r'deadlock detected', 'deadlock'),
            (r'deadlock', 'deadlock_simple'),
        ],
        'REPLICATION_ERROR': [
            (r'replication', 'replication'),
            (r'mirroring', 'mirroring'),
            (r'syncing', 'syncing'),
        ],
        'DISK_ERROR': [
            (r'disk full', 'disk_full'),
            (r'no space left', 'no_space'),
            (r'I/O error', 'io_error'),
        ],
        'CONNECTION_ERROR': [
            (r'too many clients', 'too_many_clients'),
            (r'authentication failed', 'auth_failed'),
        ],
        'QUERY_ERROR': [
            (r'syntax error', 'syntax_error'),
            (r'division by zero', 'div_zero'),
            (r'duplicate key', 'duplicate_key'),
        ],
    }
    
    def parse_line(self, line: str, category: str) -> Optional[ParsedLogEntry]:
        try:
            match = self.CSV_PATTERN.match(line.strip())
            if not match:
                return None
            
            data = match.groupdict()
            timestamp = self._parse_timestamp(data['timestamp'])
            error_type, error_subtype = self._classify_error(
                data['message'], 
                data.get('detail', ''),
                data.get('hint', '')
            )
            
            return ParsedLogEntry(
                timestamp=timestamp,
                user=data['user'],
                database=data['database'],
                pid=int(data['pid']) if data['pid'] else 0,
                host=data['host'],
                segment=data.get('segment', ''),
                severity=data['severity'],
                sql_state=data['sql_state'],
                message=data['message'],
                detail=data['detail'] if data['detail'] else None,
                hint=data['hint'] if data['hint'] else None,
                query=data['query'] if data['query'] and data['query'] != '""' else None,
                raw_line=line,
                category=category,
                error_type=error_type,
                error_subtype=error_subtype,
            )
        except Exception:
            return None
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        formats = [
            '%Y-%m-%d %H:%M:%S.%f %Z',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S %Z',
            '%Y-%m-%d %H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(ts_str, fmt)
            except ValueError:
                continue
        
        try:
            date_part = ts_str.split('.')[0]
            return datetime.strptime(date_part, '%Y-%m-%d %H:%M:%S')
        except:
            return datetime.now()
    
    def _classify_error(self, message: str, detail: str, hint: str) -> tuple:
        text_to_check = f"{message} {detail} {hint}"
        
        for error_type, patterns in self.ERROR_PATTERNS.items():
            for pattern, subtype in patterns:
                if re.search(pattern, text_to_check, re.IGNORECASE):
                    return error_type, subtype
        
        return None, None


class LogAggregator:
    """Aggregates and summarizes parsed log entries"""
    
    def __init__(self):
        self.entries: List[ParsedLogEntry] = []
    
    def add_entry(self, entry: ParsedLogEntry):
        self.entries.append(entry)
    
    def get_summary(self) -> Dict[str, Any]:
        if not self.entries:
            return {
                'total_entries': 0,
                'message': 'No errors found'
            }
        
        self.entries.sort(key=lambda e: e.timestamp)
        
        error_types = defaultdict(list)
        hosts = defaultdict(list)
        segments = defaultdict(list)
        
        for entry in self.entries:
            error_types[entry.error_type or 'UNKNOWN'].append(entry)
            if entry.host:
                hosts[entry.host].append(entry)
            if entry.segment:
                segments[entry.segment].append(entry)
        
        # Top errors
        message_groups = defaultdict(list)
        for entry in self.entries:
            message_groups[entry.message[:200]].append(entry)
        
        sorted_messages = sorted(message_groups.items(), key=lambda x: len(x[1]), reverse=True)
        
        top_errors = []
        for message, entries in sorted_messages[:10]:
            example = entries[0]
            top_errors.append({
                'count': len(entries),
                'message': message,
                'severity': example.severity,
                'error_type': example.error_type,
                'first_seen': min(e.timestamp for e in entries).isoformat(),
                'last_seen': max(e.timestamp for e in entries).isoformat(),
            })
        
        return {
            'total_entries': len(self.entries),
            'time_range': {
                'from': self.entries[0].timestamp.isoformat(),
                'to': self.entries[-1].timestamp.isoformat(),
            },
            'severity_distribution': dict(Counter(e.severity for e in self.entries)),
            'error_types': {
                etype: {
                    'count': len(entries),
                    'first_seen': min(e.timestamp for e in entries).isoformat(),
                    'last_seen': max(e.timestamp for e in entries).isoformat(),
                    'example_messages': list(dict.fromkeys(e.message for e in entries))[:3],
                    'affected_hosts': list(set(e.host for e in entries if e.host)),
                    'affected_segments': list(set(e.segment for e in entries if e.segment)),
                }
                for etype, entries in sorted(error_types.items(), key=lambda x: len(x[1]), reverse=True)
            },
            'hosts_affected': {
                host: len(entries)
                for host, entries in hosts.items()
            },
            'segments_affected': {
                seg: len(entries)
                for seg, entries in segments.items()
            },
            'top_errors': top_errors,
        }


def find_log_files(directory: str) -> List[Path]:
    """Find all log files recursively"""
    log_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(('.csv', '.csv.gz', '.log', '.log.gz')):
                log_files.append(Path(root) / file)
    
    return log_files


def read_file_lines(filepath: Path) -> List[str]:
    """Read all lines from file (supports gzip)"""
    if filepath.suffix == '.gz':
        with gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore') as f:
            return f.readlines()
    else:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.readlines()


def print_report(summary: Dict[str, Any]):
    """Print formatted report to console"""
    print("\n" + "=" * 70)
    print(" GREENPLUM LOG ANALYSIS REPORT")
    print("=" * 70)
    
    print(f"\nTotal errors found: {summary['total_entries']}")
    
    if summary['total_entries'] == 0:
        print(summary.get('message', 'No errors found'))
        print("\n" + "=" * 70)
        return
    
    time_range = summary['time_range']
    print(f"Time range: {time_range['from']} - {time_range['to']}")
    
    # Severity distribution
    print(f"\n--- Severity Distribution ---")
    for severity, count in summary['severity_distribution'].items():
        bar = "#" * min(count, 50)
        print(f"  {severity:10s}: {count:5d} {bar}")
    
    # Error types
    print(f"\n--- Error Types ---")
    for error_type, info in summary['error_types'].items():
        print(f"\n  [{error_type}] - {info['count']} occurrences")
        print(f"  Period: {info['first_seen']} - {info['last_seen']}")
        
        if info['affected_hosts']:
            print(f"  Hosts: {', '.join(info['affected_hosts'])}")
        if info['affected_segments']:
            print(f"  Segments: {', '.join(info['affected_segments'][:5])}")
        
        print(f"  Example messages:")
        for msg in info['example_messages'][:2]:
            print(f"    - {msg[:120]}")
    
    # Top errors
    print(f"\n--- Top 10 Most Frequent Errors ---")
    for i, error in enumerate(summary['top_errors'][:10], 1):
        print(f"  {i:2d}. [{error['count']}x] {error['severity']}: {error['message'][:100]}")
    
    # Affected hosts
    if summary['hosts_affected']:
        print(f"\n--- Affected Hosts ---")
        for host, count in summary['hosts_affected'].items():
            print(f"  {host}: {count} errors")
    
    # Affected segments
    if summary['segments_affected']:
        print(f"\n--- Affected Segments ---")
        for seg, count in sorted(summary['segments_affected'].items()):
            print(f"  {seg}: {count} errors")
    
    print("\n" + "=" * 70)


def main():
    # Parse arguments
    if len(sys.argv) < 2:
        print("=" * 70)
        print(" GREENPLUM LOG ANALYZER")
        print("=" * 70)
        print("\nUsage:")
        print("  python gp_analyzer.py <log_directory>")
        print("  python gp_analyzer.py <log_file.csv>")
        print("\nExamples:")
        print("  python gp_analyzer.py C:\\logs\\gpAdminLogs")
        print("  python gp_analyzer.py C:\\Users\\FunPlus\\Documents\\AiLog\\err")
        print("  python gp_analyzer.py ./test_logs")
        print("=" * 70)
        sys.exit(0)
    
    log_path = sys.argv[1]
    
    print("=" * 70)
    print(" GREENPLUM LOG ANALYZER")
    print("=" * 70)
    print(f"Path: {log_path}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if path exists
    path = Path(log_path)
    if not path.exists():
        print(f"\n[ERROR] Path not found: {log_path}")
        sys.exit(1)
    
    # Find log files
    print("\n[INFO] Searching for log files...")
    
    if path.is_file():
        log_files = [path]
    else:
        log_files = find_log_files(log_path)
    
    if not log_files:
        print("[WARNING] No log files found (.csv, .csv.gz, .log)")
        sys.exit(0)
    
    print(f"[INFO] Found {len(log_files)} file(s):")
    for f in log_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  - {f.name} ({size_mb:.1f} MB)")
    
    # Parse logs
    print("\n[INFO] Parsing log files...")
    parser = LogParser()
    aggregator = LogAggregator()
    
    total_lines = 0
    error_entries = 0
    
    for filepath in log_files:
        print(f"\n  Processing: {filepath.name}...")
        
        try:
            lines = read_file_lines(filepath)
            total_lines += len(lines)
            
            file_errors = 0
            for line in lines:
                entry = parser.parse_line(line, 'log')
                if entry and entry.severity in ['ERROR', 'FATAL', 'PANIC']:
                    aggregator.add_entry(entry)
                    file_errors += 1
            
            error_entries += file_errors
            print(f"    Lines: {len(lines)}, Errors: {file_errors}")
            
        except Exception as e:
            print(f"    [ERROR] Failed to process file: {e}")
    
    # Print summary
    print(f"\n[INFO] Total lines processed: {total_lines}")
    print(f"[INFO] Total errors extracted: {error_entries}")
    
    summary = aggregator.get_summary()
    print_report(summary)
    
    # Save JSON report
    json_path = "gp_log_report.json"
    import json
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n[INFO] JSON report saved to: {json_path}")


if __name__ == '__main__':
    main()