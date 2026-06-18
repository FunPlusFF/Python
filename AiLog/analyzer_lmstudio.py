# analyzer_lmstudio.py - Финальная версия с фильтрацией
import sys
import json
import time
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

from prompt_builder_gemma import GemmaPromptBuilder
from lmstudio_client import LMStudioClient


class LogAnalyzerLMStudio:
    """Анализатор логов Greenplum с LM Studio"""
    
    def __init__(self):
        self.client = LMStudioClient()
        self.prompt_builder = GemmaPromptBuilder()
    
    def aggregate_errors(self, entries: list) -> dict:
        """Агрегация ошибок для анализа"""
        
        if not entries:
            return {'total_errors': 0, 'message': 'Ошибок не обнаружено'}
        
        entries.sort(key=lambda e: e['timestamp'])
        
        error_types = defaultdict(lambda: {
            'count': 0, 'hosts': set(), 'segments': set(), 'examples': []
        })
        
        severity_count = Counter()
        hosts_set = set()
        segments_set = set()
        databases_set = set()
        source_files = set()
        
        for entry in entries:
            etype = entry.get('error_type', 'UNKNOWN')
            error_types[etype]['count'] += 1
            error_types[etype]['hosts'].add(entry.get('host', ''))
            error_types[etype]['segments'].add(entry.get('segment', ''))
            
            if len(error_types[etype]['examples']) < 3:
                error_types[etype]['examples'].append(entry)
            
            severity_count[entry.get('severity', '?')] += 1
            if entry.get('host'):
                hosts_set.add(entry['host'])
            if entry.get('segment'):
                segments_set.add(entry['segment'])
            if entry.get('database'):
                databases_set.add(entry['database'])
            if entry.get('source_file'):
                source_files.add(entry['source_file'])
        
        critical = [
            {
                'timestamp': e['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'severity': e.get('severity', ''),
                'host': e.get('host', ''),
                'segment': e.get('segment', ''),
                'message': e.get('message', '')[:200],
                'detail': e.get('detail', '')[:200] if e.get('detail') else '',
            }
            for e in entries 
            if e.get('severity') in ['PANIC', 'FATAL']
        ]
        
        formatted_types = {}
        for etype, info in error_types.items():
            formatted_types[etype] = {
                'count': info['count'],
                'hosts': list(info['hosts']),
                'segments': list(info['segments']),
                'examples': [
                    {
                        'severity': ex.get('severity', ''),
                        'message': ex.get('message', '')[:200],
                        'detail': ex.get('detail', '')[:200] if ex.get('detail') else '',
                        'query': ex.get('query', '')[:200] if ex.get('query') else '',
                        'host': ex.get('host', ''),
                        'file': ex.get('source_file', ''),
                    }
                    for ex in info['examples'][:2]
                ]
            }
        
        return {
            'total_errors': len(entries),
            'time_info': {
                'first_error': entries[0]['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'last_error': entries[-1]['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
            },
            'severity_distribution': dict(severity_count),
            'error_types': formatted_types,
            'critical_events': critical[:5],
            'affected_hosts': list(hosts_set),
            'affected_segments': list(segments_set),
            'databases': list(databases_set),
            'source_files': list(source_files),
        }


def extract_json_from_response(content: str) -> dict:
    """Извлекает JSON из ответа модели"""
    
    json_match = re.search(r'```json\s*\n(.*?)\n```', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass
    
    json_start = content.find('{')
    json_end = content.rfind('}')
    
    if json_start >= 0 and json_end > json_start:
        json_str = content[json_start:json_end + 1]
        try:
            return json.loads(json_str)
        except:
            pass
    
    return {'raw_analysis': content}


def print_analysis(result: dict):
    """Вывод анализа на русском языке"""
    
    if not result.get('success'):
        print(f"\n{'=' * 70}")
        print(f" ❌ ОШИБКА: {result.get('error', 'Неизвестная ошибка')}")
        print(f"{'=' * 70}")
        return
    
    analysis = result.get('analysis', {})
    usage = result.get('usage', {})
    
    print("\n" + "=" * 70)
    print("           🏥 AI-АНАЛИЗ ОШИБОК GREENPLUM")
    print("=" * 70)
    
    # Определяем язык ключей
    is_russian = any(k in analysis for k in ['первопричина', 'анализ', 'рекомендации'])
    
    if is_russian:
        root_cause = analysis.get('первопричина', '')
        error_analysis = analysis.get('анализ', '')
        components = analysis.get('затронутые_компоненты', [])
        recommendations = analysis.get('рекомендации', [])
        config_changes = analysis.get('изменения_конфигурации', [])
        prevention = analysis.get('профилактика', [])
    else:
        root_cause = analysis.get('root_cause', '')
        error_analysis = analysis.get('error_analysis', '')
        components = analysis.get('affected_components', [])
        recommendations = analysis.get('recommendations', [])
        config_changes = analysis.get('configuration_changes', [])
        prevention = analysis.get('prevention_tips', [])
    
    if root_cause:
        print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ 🔍 ПЕРВОПРИЧИНА                                                      │
├──────────────────────────────────────────────────────────────────────┤
│ {root_cause[:66]:<66} │
└──────────────────────────────────────────────────────────────────────┘""")
    
    if error_analysis:
        print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ 📊 ДЕТАЛЬНЫЙ АНАЛИЗ                                                  │
├──────────────────────────────────────────────────────────────────────┤""")
        words = error_analysis.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= 66:
                current += (" " + word if current else word)
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        
        for line in lines[:10]:
            print(f"│ {line:<66} │")
        print(f"└──────────────────────────────────────────────────────────────────────┘")
    
    if components:
        print(f"\n🖥️  ЗАТРОНУТЫЕ КОМПОНЕНТЫ:")
        for comp in components:
            print(f"   • {comp}")
    
    if recommendations:
        print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ 🔧 ПЛАН ИСПРАВЛЕНИЯ                                                  │
├──────────────────────────────────────────────────────────────────────┤""")
        
        for i, rec in enumerate(recommendations, 1):
            priority = rec.get('приоритет', rec.get('priority', 'средний')).upper()
            action = rec.get('действие', rec.get('action', '?'))
            command = rec.get('команда', rec.get('command', ''))
            reason = rec.get('обоснование', rec.get('reason', ''))
            
            emoji = {
                'КРИТИЧЕСКИЙ': '🔴', 'CRITICAL': '🔴',
                'ВЫСОКИЙ': '🟠', 'HIGH': '🟠',
                'СРЕДНИЙ': '🟡', 'MEDIUM': '🟡',
                'НИЗКИЙ': '🟢', 'LOW': '🟢'
            }.get(priority, '⚪')
            
            print(f"""│
│ {i}. {emoji} [{priority}] {action[:55]}
│""")
            
            if command:
                while len(command) > 60:
                    print(f"│    💻 {command[:58]}")
                    command = command[58:]
                print(f"│    💻 {command}")
            
            if reason:
                while len(reason) > 60:
                    print(f"│    📝 {reason[:58]}")
                    reason = reason[58:]
                print(f"│    📝 {reason}")
        
        print(f"└──────────────────────────────────────────────────────────────────────┘")
    
    if config_changes:
        print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ ⚙️  РЕКОМЕНДАЦИИ ПО КОНФИГУРАЦИИ                                     │
├──────────────────────────────────────────────────────────────────────┤""")
        for change in config_changes:
            param = change.get('параметр', change.get('parameter', '?'))
            recommended = change.get('рекомендуемое', change.get('recommended', '?'))
            reason = change.get('обоснование', change.get('reason', ''))
            
            print(f"│ • {param} → {recommended}")
            if reason:
                print(f"│   {reason[:64]}")
        print(f"└──────────────────────────────────────────────────────────────────────┘")
    
    if prevention:
        print(f"\n💡 ПРОФИЛАКТИКА:")
        for tip in prevention:
            print(f"   ✓ {tip}")
    
    if 'raw_analysis' in analysis and len(analysis) == 1:
        print(f"\n📄 Ответ модели:")
        print(analysis['raw_analysis'][:1500])
    
    if usage:
        pt = usage.get('prompt_tokens', 0)
        ct = usage.get('completion_tokens', 0)
        tt = usage.get('total_tokens', 0)
        print(f"""
┌──────────────────────────────────────────────────────────────────────┐
│ 📈 ТОКЕНЫ: Промпт {pt} | Ответ {ct} | Всего {tt}                          │
└──────────────────────────────────────────────────────────────────────┘""")
    
    print()


def find_log_files(path: Path) -> list:
    """Поиск всех лог-файлов"""
    if path.is_file():
        return [path]
    
    log_files = []
    for pattern in ['*.csv', '*.log']:
        log_files.extend(path.glob(pattern))
    
    log_files.sort(key=lambda f: f.name)
    return log_files


def parse_logs(log_files: list, time_from: datetime = None, time_to: datetime = None) -> list:
    """Парсинг всех файлов с фильтрацией по времени"""
    sys.path.insert(0, str(Path(__file__).parent))
    from main import LogParser, read_file_lines
    
    parser = LogParser(time_from=time_from, time_to=time_to)
    all_entries = []
    
    for filepath in log_files:
        print(f"  Обработка: {filepath.name}...")
        parser.current_file = filepath.name
        
        lines = read_file_lines(filepath)
        file_entries = []
        
        for line in lines:
            entry = parser.parse_line(line)
            if entry:
                file_entries.append(entry)
        
        all_entries.extend(file_entries)
        print(f"    Строк: {len(lines)}, найдено ошибок: {len(file_entries)}")
    
    return all_entries


def main():
    parser_arg = argparse.ArgumentParser(
        description='Анализатор логов Greenplum с AI (LM Studio + Gemma 4)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python analyzer_lmstudio.py logs/
  python analyzer_lmstudio.py logs/ --from "2026-06-18 14:00:00" --to "2026-06-18 15:00:00"
  python analyzer_lmstudio.py logs/ --last 2h
  python analyzer_lmstudio.py error.csv
        """
    )
    
    parser_arg.add_argument('path', type=str, help='Путь к файлу или папке с логами')
    
    parser_arg.add_argument(
        '--from', dest='time_from', type=str, default=None,
        help='Начало периода (формат: "YYYY-MM-DD HH:MM:SS")'
    )
    
    parser_arg.add_argument(
        '--to', dest='time_to', type=str, default=None,
        help='Конец периода (формат: "YYYY-MM-DD HH:MM:SS")'
    )
    
    parser_arg.add_argument(
        '--last', type=str, default=None,
        help='Анализ за последний период (например: 2h, 30m, 1d)'
    )
    
    parser_arg.add_argument(
        '--no-ai', action='store_true',
        help='Только парсинг без AI анализа'
    )
    
    args = parser_arg.parse_args()
    
    print("=" * 70)
    print(" 🟢 АНАЛИЗАТОР ЛОГОВ GREENPLUM + LM STUDIO (GEMMA 4)")
    print("=" * 70)
    
    # Парсим время
    time_from = None
    time_to = None
    
    if args.time_from:
        try:
            time_from = datetime.strptime(args.time_from, '%Y-%m-%d %H:%M:%S')
        except:
            print(f"[ERROR] Неверный формат времени: {args.time_from}")
            sys.exit(1)
    
    if args.time_to:
        try:
            time_to = datetime.strptime(args.time_to, '%Y-%m-%d %H:%M:%S')
        except:
            print(f"[ERROR] Неверный формат времени: {args.time_to}")
            sys.exit(1)
    
    if args.last:
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
            
            print(f"[INFO] Анализ за последние: {args.last}")
        else:
            print(f"[ERROR] Неверный формат --last. Используйте: 2h, 30m, 1d")
            sys.exit(1)
    
    input_path = Path(args.path)
    
    if not input_path.exists():
        print(f"[ERROR] Путь не найден: {input_path}")
        sys.exit(1)
    
    print(f"Путь: {input_path}")
    
    if time_from:
        print(f"Период: с {time_from.strftime('%Y-%m-%d %H:%M:%S')}", end='')
    if time_to:
        print(f" по {time_to.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print()
    
    # Поиск файлов
    print(f"\n[INFO] Поиск лог-файлов...")
    log_files = find_log_files(input_path)
    
    if not log_files:
        print(f"[ERROR] Файлы .csv или .log не найдены")
        sys.exit(1)
    
    total_size = sum(f.stat().st_size for f in log_files) / (1024*1024)
    print(f"[INFO] Найдено файлов: {len(log_files)} (общий размер: {total_size:.1f} MB)")
    for f in log_files:
        print(f"  - {f.name}")
    
    # Парсинг
    print(f"\n[INFO] Парсинг логов...")
    entries = parse_logs(log_files, time_from, time_to)
    
    print(f"\n[INFO] Всего найдено ошибок/предупреждений: {len(entries)}")
    
    if not entries:
        print("[INFO] В указанном диапазоне ошибок не найдено")
        sys.exit(0)
    
    # Сохранение распарсенных данных
    output_data = {
        'parse_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_errors': len(entries),
        'time_filter': {
            'from': time_from.strftime('%Y-%m-%d %H:%M:%S') if time_from else None,
            'to': time_to.strftime('%Y-%m-%d %H:%M:%S') if time_to else None,
        },
        'files': [f.name for f in log_files],
        'errors': [
            {
                'timestamp': e['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                'severity': e['severity'],
                'error_type': e['error_type'],
                'message': e['message'][:200],
                'host': e.get('host', ''),
                'segment': e.get('segment', ''),
                'file': e.get('source_file', ''),
            }
            for e in entries
        ]
    }
    
    with open('parsed_errors.json', 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)
    print("[INFO] Результат сохранен: parsed_errors.json")
    
    if args.no_ai:
        print("\n[INFO] Пропуск AI анализа (флаг --no-ai)")
        sys.exit(0)
    
    # Проверка LM Studio
    print(f"\n[INFO] Проверка подключения к LM Studio...")
    client = LMStudioClient()
    status = client.test_connection()
    
    if not status.get('connected'):
        print(f"[ERROR] LM Studio не доступен!")
        print("Запустите LM Studio и локальный сервер на порту 1234")
        sys.exit(1)
    
    print(f"[OK] LM Studio подключен")
    
    # Агрегация
    analyzer = LogAnalyzerLMStudio()
    aggregated = analyzer.aggregate_errors(entries)
    
    print(f"[INFO] Типов ошибок: {len(aggregated['error_types'])}")
    
    with open('aggregated_report.json', 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False, default=str)
    
    # Промпт и запрос
    user_prompt = analyzer.prompt_builder.build_prompt(aggregated)
    
    print(f"\n[INFO] Отправка запроса в Gemma 4 12B...")
    print(f"[INFO] Размер промпта: {len(user_prompt)} символов")
    
    start_time = time.time()
    
    result = client.analyze_logs(
        system_prompt=GemmaPromptBuilder.SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.1,
        max_tokens=4000
    )
    
    elapsed = time.time() - start_time
    print(f"[INFO] Ответ получен за {elapsed:.1f} сек")
    
    # Извлечение JSON
    if result.get('success'):
        raw = result['analysis'].get('raw_analysis', '')
        if raw:
            result['analysis'] = extract_json_from_response(raw)
    
    # Вывод и сохранение
    print_analysis(result)
    
    with open('ai_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print(f"[INFO] Результат сохранен: ai_analysis.json")


if __name__ == '__main__':
    main()