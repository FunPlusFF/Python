# output.py
import json
from datetime import datetime
from typing import Dict, Any

class OutputFormatter:
    """Форматирование результатов анализа"""
    
    @staticmethod
    def to_json(report: Dict[str, Any], pretty: bool = True) -> str:
        """Вывод в JSON формате"""
        if pretty:
            return json.dumps(report, indent=2, ensure_ascii=False)
        return json.dumps(report, ensure_ascii=False)
    
    @staticmethod
    def to_text(report: Dict[str, Any]) -> str:
        """Вывод в читаемом текстовом формате"""
        lines = []
        lines.append("=" * 70)
        lines.append("           ОТЧЕТ АНАЛИЗА ЛОГОВ GREENPLUM")
        lines.append("=" * 70)
        lines.append(f"Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Общая статистика
        lines.append("─" * 70)
        lines.append("ОБЩАЯ СТАТИСТИКА")
        lines.append("─" * 70)
        lines.append(f"Всего записей с ошибками: {report.get('total_entries', 0)}")
        
        time_range = report.get('time_range', {})
        if time_range and time_range != 'N/A':
            lines.append(f"Период: {time_range.get('from', '?')} — {time_range.get('to', '?')}")
            lines.append(f"Длительность: {time_range.get('duration_seconds', 0):.0f} сек")
        
        # Распределение по severity
        sev_dist = report.get('severity_distribution', {})
        if sev_dist:
            lines.append("\nРаспределение по уровню серьезности:")
            for severity, count in sev_dist.items():
                bar = "█" * min(count, 50)
                lines.append(f"  {severity:10s}: {count:5d} {bar}")
        
        # Типы ошибок
        error_types = report.get('error_types', {})
        if error_types:
            lines.append("\n" + "─" * 70)
            lines.append("ТИПЫ ОШИБОК")
            lines.append("─" * 70)
            
            for error_type, info in error_types.items():
                lines.append(f"\n[{error_type}] — {info['count']} шт.")
                lines.append(f"  Период: {info['first_seen']} — {info['last_seen']}")
                
                if info.get('affected_hosts'):
                    lines.append(f"  Хосты: {', '.join(info['affected_hosts'])}")
                
                if info.get('affected_segments'):
                    lines.append(f"  Сегменты: {', '.join(info['affected_segments'][:5])}")
                
                if info.get('example_messages'):
                    lines.append("  Примеры сообщений:")
                    for msg in info['example_messages'][:3]:
                        lines.append(f"    • {msg[:150]}")
        
        # Пиковая активность
        peak = report.get('peak_activity')
        if peak:
            lines.append("\n" + "─" * 70)
            lines.append("ПИКОВАЯ АКТИВНОСТЬ")
            lines.append("─" * 70)
            lines.append(f"Время пика: {peak['time']}")
            lines.append(f"Количество ошибок: {peak['error_count']}")
            if peak.get('error_types'):
                lines.append("Типы ошибок в пиковый период:")
                for etype, count in peak['error_types'].items():
                    lines.append(f"  • {etype}: {count}")
        
        # Критические события
        critical = report.get('critical_events', [])
        if critical:
            lines.append("\n" + "─" * 70)
            lines.append("КРИТИЧЕСКИЕ СОБЫТИЯ (PANIC/FATAL)")
            lines.append("─" * 70)
            for event in critical[:10]:  # Первые 10
                lines.append(f"\n[{event['timestamp']}] {event['severity']}")
                lines.append(f"  Хост: {event['host']}, Сегмент: {event['segment']}")
                lines.append(f"  Сообщение: {event['message'][:200]}")
                if event.get('detail'):
                    lines.append(f"  Детали: {event['detail'][:200]}")
        
        # Топ ошибок
        top_errors = report.get('top_errors', [])
        if top_errors:
            lines.append("\n" + "─" * 70)
            lines.append("ТОП-10 САМЫХ ЧАСТЫХ ОШИБОК")
            lines.append("─" * 70)
            for i, error in enumerate(top_errors, 1):
                lines.append(f"\n{i}. [{error['count']} раз] {error['severity']}")
                lines.append(f"   {error['message'][:150]}")
                if error.get('example_hint'):
                    lines.append(f"   Подсказка: {error['example_hint'][:150]}")
        
        lines.append("\n" + "=" * 70)
        lines.append("КОНЕЦ ОТЧЕТА")
        lines.append("=" * 70)
        
        return "\n".join(lines)