# analyzer_with_llm.py - Полный анализатор с LLM
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict, Counter

# Импортируем наши модули
from prompt_builder import PromptBuilder
from deepseek_client import DeepSeekClient


class LogAnalyzerWithAI:
    """Анализатор логов с интеграцией DeepSeek"""
    
    def __init__(self, api_key: str = None):
        # API ключ из аргументов или переменной окружения
        self.api_key = api_key or os.environ.get('DEEPSEEK_API_KEY', '')
        self.deepseek = DeepSeekClient(self.api_key) if self.api_key else None
        self.prompt_builder = PromptBuilder()
    
    def aggregate_errors(self, entries: list) -> dict:
        """Агрегация ошибок для передачи в LLM"""
        
        if not entries:
            return {
                'total_errors': 0,
                'message': 'Ошибок не найдено'
            }
        
        # Сортировка по времени
        entries.sort(key=lambda e: e['timestamp'])
        
        # Временная информация
        first_error = entries[0]['timestamp']
        last_error = entries[-1]['timestamp']
        
        # Поиск пика ошибок (5-минутные интервалы)
        intervals = defaultdict(int)
        for entry in entries:
            minute = (entry['timestamp'].minute // 5) * 5
            interval_key = entry['timestamp'].replace(minute=minute, second=0, microsecond=0)
            intervals[interval_key] += 1
        
        peak_time = max(intervals, key=intervals.get) if intervals else None
        
        # Группировка по типам ошибок
        error_types = defaultdict(lambda: {
            'count': 0,
            'hosts': set(),
            'segments': set(),
            'examples': []
        })
        
        severity_count = Counter()
        hosts_affected = set()
        segments_affected = set()
        databases = set()
        
        for entry in entries:
            etype = entry.get('error_type', 'UNKNOWN')
            error_types[etype]['count'] += 1
            error_types[etype]['hosts'].add(entry.get('host', ''))
            error_types[etype]['segments'].add(entry.get('segment', ''))
            
            if len(error_types[etype]['examples']) < 3:
                error_types[etype]['examples'].append(entry)
            
            severity_count[entry.get('severity', 'UNKNOWN')] += 1
            if entry.get('host'):
                hosts_affected.add(entry['host'])
            if entry.get('segment'):
                segments_affected.add(entry['segment'])
            if entry.get('database'):
                databases.add(entry['database'])
        
        # Топ ошибок
        message_count = Counter(e['message'][:150] for e in entries)
        top_errors = [
            {'count': count, 'message': msg}
            for msg, count in message_count.most_common(10)
        ]
        
        # Критические события
        critical = [
            e for e in entries 
            if e.get('severity') in ['PANIC', 'FATAL']
        ]
        critical.sort(key=lambda e: e['timestamp'])
        
        # Преобразуем sets в списки для JSON
        formatted_types = {}
        for etype, info in error_types.items():
            formatted_types[etype] = {
                'count': info['count'],
                'hosts': list(info['hosts']),
                'segments': list(info['segments']),
                'examples': [
                    {
                        'severity': ex.get('severity', ''),
                        'message': ex.get('message', ''),
                        'detail': ex.get('detail', ''),
                        'query': ex.get('query', ''),
                        'host': ex.get('host', ''),
                        'segment': ex.get('segment', ''),
                    }
                    for ex in info['examples'][:3]
                ]
            }
        
        return {
            'total_errors': len(entries),
            'time_info': {
                'first_error': first_error.strftime('%Y-%m-%d %H:%M:%S'),
                'last_error': last_error.strftime('%Y-%m-%d %H:%M:%S'),
                'peak_time': peak_time.strftime('%Y-%m-%d %H:%M:%S') if peak_time else 'N/A',
            },
            'severity_distribution': dict(severity_count),
            'error_types': formatted_types,
            'top_errors': top_errors,
            'critical_events': [
                {
                    'timestamp': e['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                    'severity': e.get('severity', ''),
                    'host': e.get('host', ''),
                    'segment': e.get('segment', ''),
                    'message': e.get('message', ''),
                    'detail': e.get('detail', ''),
                }
                for e in critical[:10]
            ],
            'affected_hosts': list(hosts_affected),
            'affected_segments': list(segments_affected),
            'databases': list(databases),
        }
    
    def analyze_with_ai(self, aggregated_data: dict) -> dict:
        """Отправка агрегированных данных в DeepSeek"""
        
        if not self.deepseek:
            return {
                'success': False,
                'error': 'API ключ не настроен. Установите DEEPSEEK_API_KEY или передайте api_key'
            }
        
        # Проверяем соединение
        if not self.deepseek.test_connection():
            return {
                'success': False,
                'error': 'Не удалось подключиться к DeepSeek API. Проверьте ключ и интернет.'
            }
        
        # Формируем промпт
        system_prompt = self.prompt_builder.SYSTEM_PROMPT
        user_prompt = self.prompt_builder.build_compact_prompt(aggregated_data)
        
        print("\n[INFO] Отправка запроса в DeepSeek API...")
        print(f"[INFO] Размер промпта: {len(user_prompt)} символов")
        
        # Отправляем запрос
        result = self.deepseek.analyze_logs(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.1,  # Низкая температура для точных ответов
            max_tokens=2000
        )
        
        return result


def print_ai_analysis(result: dict):
    """Красивый вывод результатов анализа от LLM"""
    
    if not result.get('success'):
        print(f"\n[ERROR] {result.get('error', 'Unknown error')}")
        if result.get('details'):
            print(f"Details: {result['details'][:500]}")
        return
    
    analysis = result.get('analysis', {})
    usage = result.get('usage', {})
    
    print("\n" + "=" * 70)
    print("           AI АНАЛИЗ ОШИБОК GREENPLUM")
    print("=" * 70)
    
    # Если есть структурированный JSON ответ
    if 'root_cause' in analysis:
        print(f"\n🔍 ПЕРВОПРИЧИНА:")
        print(f"   {analysis['root_cause']}")
        
        if 'error_analysis' in analysis:
            print(f"\n📊 АНАЛИЗ ЦЕПОЧКИ СОБЫТИЙ:")
            print(f"   {analysis['error_analysis']}")
        
        if 'affected_components' in analysis:
            print(f"\n🖥️ ЗАТРОНУТЫЕ КОМПОНЕНТЫ:")
            for comp in analysis['affected_components']:
                print(f"   • {comp}")
        
        if 'recommendations' in analysis:
            print(f"\n🔧 РЕКОМЕНДАЦИИ ПО ИСПРАВЛЕНИЮ:")
            for i, rec in enumerate(analysis['recommendations'], 1):
                priority_emoji = {
                    'high': '🔴',
                    'medium': '🟡',
                    'low': '🟢'
                }.get(rec.get('priority', 'medium'), '⚪')
                
                print(f"\n   {i}. {priority_emoji} [{rec.get('priority', '?').upper()}] {rec.get('action', '')}")
                if rec.get('command'):
                    print(f"      Команда: {rec['command']}")
                print(f"      Причина: {rec.get('reason', '')}")
        
        if 'configuration_changes' in analysis:
            print(f"\n⚙️ ИЗМЕНЕНИЯ КОНФИГУРАЦИИ:")
            for change in analysis['configuration_changes']:
                print(f"   • {change.get('parameter', '?')}: → {change.get('recommended', '?')}")
                print(f"     {change.get('reason', '')}")
        
        if 'prevention_tips' in analysis:
            print(f"\n💡 СОВЕТЫ ПО ПРЕДОТВРАЩЕНИЮ:")
            for tip in analysis['prevention_tips']:
                print(f"   • {tip}")
    
    else:
        # Если модель вернула текст вместо JSON
        print(f"\n{analysis.get('raw_analysis', 'Нет ответа')}")
    
    # Статистика использования
    if usage:
        print(f"\n{'─' * 70}")
        print(f"📈 Использование токенов:")
        print(f"   Промпт: {usage.get('prompt_tokens', '?')}")
        print(f"   Ответ: {usage.get('completion_tokens', '?')}")
        print(f"   Всего: {usage.get('total_tokens', '?')}")
    
    print("\n" + "=" * 70)


# Для тестирования без API (демо-режим)
def demo_analysis(aggregated_data: dict) -> dict:
    """Демо-анализ без API (для тестирования)"""
    
    # Простая логика для демонстрации
    error_types = aggregated_data.get('error_types', {})
    severity = aggregated_data.get('severity_distribution', {})
    
    root_cause = "Недостаток памяти на сегменте"
    if 'INTERCONNECT_ERROR' in error_types and 'OUT_OF_MEMORY' in error_types:
        root_cause = "Каскадный сбой interconnect из-за OOM на одном из сегментов"
    elif 'PANIC' in severity:
        root_cause = "Критический сбой сегмента (PANIC), возможно аппаратная проблема"
    elif 'DUPLICATE_KEY' in error_types:
        root_cause = "Проблемы с целостностью данных при вставке"
    
    return {
        'success': True,
        'analysis': {
            'root_cause': root_cause,
            'error_analysis': f"Обнаружено {aggregated_data.get('total_errors', 0)} ошибок. "
                            f"Основные типы: {', '.join(error_types.keys())}.",
            'recommendations': [
                {
                    'priority': 'high',
                    'action': 'Проверить использование памяти на сегментах',
                    'command': 'gpssh -f seg_hosts "free -h"',
                    'reason': 'Большинство ошибок связано с нехваткой памяти'
                }
            ],
            'configuration_changes': [
                {
                    'parameter': 'gp_vmem_protect_limit',
                    'recommended': '8192 MB',
                    'reason': 'Увеличить лимит памяти для предотвращения OOM'
                }
            ]
        },
        'usage': {'prompt_tokens': 500, 'completion_tokens': 200, 'total_tokens': 700}
    }


def main():
    # Проверяем API ключ
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    
    if not api_key:
        print("=" * 70)
        print(" ВНИМАНИЕ: DEEPSEEK_API_KEY не найден!")
        print("=" * 70)
        print("\nДля работы с DeepSeek API:")
        print("1. Зарегистрируйтесь на https://platform.deepseek.com/")
        print("2. Получите API ключ в настройках")
        print("3. Установите переменную окружения:")
        print("   PowerShell: $env:DEEPSEEK_API_KEY='ваш_ключ'")
        print("   CMD: set DEEPSEEK_API_KEY=ваш_ключ")
        print("\nБудет использован ДЕМО-РЕЖИМ без API\n")
    
    if len(sys.argv) < 2:
        print("Usage: python analyzer_with_llm.py <log_file.csv>")
        print("Example: python analyzer_with_llm.py err/test_greenplum_log.csv")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    
    if not input_path.exists():
        print(f"[ERROR] File not found: {input_path}")
        sys.exit(1)
    
    # Импортируем парсер из main.py
    sys.path.insert(0, str(Path(__file__).parent))
    from main import LogParser, read_file_lines
    
    # Парсим логи
    print("=" * 70)
    print(" GREENPLUM LOG ANALYZER WITH AI")
    print("=" * 70)
    print(f"File: {input_path}")
    
    parser = LogParser()
    entries = []
    
    if input_path.is_file():
        lines = read_file_lines(input_path)
        for line in lines:
            entry = parser.parse_line(line)
            if entry:
                entries.append(entry)
    
    print(f"Parsed errors: {len(entries)}")
    
    # Агрегируем
    analyzer = LogAnalyzerWithAI(api_key if api_key else None)
    aggregated = analyzer.aggregate_errors(entries)
    
    print(f"Aggregated: {aggregated['total_errors']} errors, "
          f"{len(aggregated['error_types'])} types")
    
    # Сохраняем агрегированные данные
    with open('aggregated_report.json', 'w', encoding='utf-8') as f:
        json.dump(aggregated, f, indent=2, ensure_ascii=False, default=str)
    print("Saved: aggregated_report.json")
    
    # Анализ через AI или демо
    if api_key:
        result = analyzer.analyze_with_ai(aggregated)
    else:
        print("\n[INFO] Используется демо-режим")
        result = demo_analysis(aggregated)
    
    # Выводим результат
    print_ai_analysis(result)
    
    # Сохраняем полный результат
    with open('ai_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)
    print("\nSaved: ai_analysis.json")


if __name__ == '__main__':
    main()