# prompt_builder.py - Формирование запроса к LLM
import json
from datetime import datetime
from typing import List, Dict, Any


class PromptBuilder:
    """Формирует промпт для LLM на основе агрегированных ошибок"""
    
    SYSTEM_PROMPT = """Ты — ведущий администратор баз данных (DBA) Greenplum с 15-летним опытом. 
Твоя задача — проанализировать агрегированный отчет об ошибках кластера MPP и предоставить диагностику.

ВАЖНЫЕ ПРАВИЛА:
1. Игнорируй шум, выявляй ПЕРВОПРИЧИНУ (root cause)
2. Проблемы на одном сегменте часто вызваны сбоем железа (память, диск, сеть)
3. Если много ошибок interconnect после OOM — это каскадный сбой из-за падения одного сегмента
4. Давай конкретные команды для исправления
5. Указывай параметры GUC, которые нужно изменить

Формат ответа СТРОГО JSON:
{
  "root_cause": "краткое описание первопричины (1-2 предложения)",
  "error_analysis": "детальный анализ цепочки событий (3-5 предложений)",
  "affected_components": ["список", "затронутых", "компонентов"],
  "recommendations": [
    {
      "priority": "high/medium/low",
      "action": "конкретное действие",
      "command": "команда для выполнения (если применимо)",
      "reason": "почему это нужно сделать"
    }
  ],
  "configuration_changes": [
    {
      "parameter": "имя параметра GUC",
      "current_suspected": "предполагаемое текущее значение",
      "recommended": "рекомендуемое значение",
      "reason": "обоснование изменения"
    }
  ],
  "prevention_tips": ["совет 1", "совет 2"]
}"""
    
    def build_prompt(self, error_summary: Dict[str, Any]) -> str:
        """Создает промпт на основе сводки ошибок"""
        
        prompt_parts = []
        
        # Базовая информация
        prompt_parts.append("# ОТЧЕТ ОБ ОШИБКАХ КЛАСТЕРА GREENPLUM")
        prompt_parts.append(f"Дата анализа: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        prompt_parts.append(f"Всего ошибок: {error_summary.get('total_errors', 0)}")
        prompt_parts.append("")
        
        # Информация о времени
        time_info = error_summary.get('time_info', {})
        if time_info:
            prompt_parts.append("## Временной диапазон")
            prompt_parts.append(f"- Начало: {time_info.get('first_error', 'N/A')}")
            prompt_parts.append(f"- Конец: {time_info.get('last_error', 'N/A')}")
            prompt_parts.append(f"- Пик ошибок: {time_info.get('peak_time', 'N/A')}")
            prompt_parts.append("")
        
        # Распределение severity
        severity = error_summary.get('severity_distribution', {})
        if severity:
            prompt_parts.append("## Распределение по серьезности")
            for sev, count in severity.items():
                prompt_parts.append(f"- {sev}: {count}")
            prompt_parts.append("")
        
        # Типы ошибок
        error_types = error_summary.get('error_types', {})
        if error_types:
            prompt_parts.append("## Типы ошибок")
            for etype, info in error_types.items():
                prompt_parts.append(f"\n### {etype} (всего: {info.get('count', 0)})")
                prompt_parts.append(f"Затронутые хосты: {', '.join(info.get('hosts', ['неизвестно']))}")
                prompt_parts.append(f"Затронутые сегменты: {', '.join(info.get('segments', ['неизвестно']))}")
                
                examples = info.get('examples', [])
                if examples:
                    prompt_parts.append("Примеры сообщений:")
                    for ex in examples[:3]:
                        prompt_parts.append(f"  - [{ex.get('severity', '?')}] {ex.get('message', '')[:200]}")
                        if ex.get('detail'):
                            prompt_parts.append(f"    Detail: {ex.get('detail', '')[:150]}")
                        if ex.get('query'):
                            prompt_parts.append(f"    Query: {ex.get('query', '')[:150]}")
                prompt_parts.append("")
        
        # Топ ошибок
        top_errors = error_summary.get('top_errors', [])
        if top_errors:
            prompt_parts.append("## Топ-5 самых частых ошибок")
            for i, err in enumerate(top_errors[:5], 1):
                prompt_parts.append(f"{i}. [{err.get('count', 0)}x] {err.get('message', '')[:150]}")
            prompt_parts.append("")
        
        # Критические события
        critical = error_summary.get('critical_events', [])
        if critical:
            prompt_parts.append("## КРИТИЧЕСКИЕ СОБЫТИЯ (PANIC/FATAL)")
            for event in critical[:5]:
                prompt_parts.append(f"- [{event.get('severity', '?')}] {event.get('timestamp', '?')}")
                prompt_parts.append(f"  Хост: {event.get('host', '?')}, Сегмент: {event.get('segment', '?')}")
                prompt_parts.append(f"  Сообщение: {event.get('message', '')[:200]}")
                if event.get('detail'):
                    prompt_parts.append(f"  Детали: {event.get('detail', '')[:150]}")
            prompt_parts.append("")
        
        # Контекст системы
        prompt_parts.append("## Системный контекст")
        hosts = error_summary.get('affected_hosts', {})
        segments = error_summary.get('affected_segments', {})
        prompt_parts.append(f"- Всего затронуто хостов: {len(hosts)}")
        prompt_parts.append(f"- Всего затронуто сегментов: {len(segments)}")
        prompt_parts.append(f"- Базы данных: {', '.join(error_summary.get('databases', ['неизвестно']))}")
        prompt_parts.append("")
        
        prompt_parts.append("## ЗАДАЧА")
        prompt_parts.append("Проанализируй ошибки, найди первопричину и предоставь план исправления в формате JSON.")
        
        return "\n".join(prompt_parts)
    
    def build_compact_prompt(self, error_summary: Dict[str, Any]) -> str:
        """Создает компактный промпт (для экономии токенов)"""
        
        # Считаем статистику
        total = error_summary.get('total_errors', 0)
        severity = error_summary.get('severity_distribution', {})
        panic_count = severity.get('PANIC', 0)
        fatal_count = severity.get('FATAL', 0)
        error_count = severity.get('ERROR', 0)
        
        # Собираем типы ошибок
        error_types_summary = []
        for etype, info in error_summary.get('error_types', {}).items():
            hosts = info.get('hosts', [])
            examples = info.get('examples', [])
            msg = examples[0].get('message', '')[:120] if examples else ''
            error_types_summary.append(
                f"- {etype}: {info.get('count', 0)} шт. на хостах {', '.join(hosts[:3])}. "
                f"Пример: {msg}"
            )
        
        # Критические события
        critical_summary = []
        for event in error_summary.get('critical_events', [])[:3]:
            critical_summary.append(
                f"- [{event.get('severity')}] {event.get('host')}/{event.get('segment')}: "
                f"{event.get('message', '')[:150]}"
            )
        
        prompt = f"""# Сводка ошибок Greenplum

Всего ошибок: {total}
Severity: PANIC={panic_count}, FATAL={fatal_count}, ERROR={error_count}

## Типы ошибок:
{chr(10).join(error_types_summary)}

## Критические события:
{chr(10).join(critical_summary) if critical_summary else 'Нет критических событий'}

## Система:
- Хостов затронуто: {len(error_summary.get('affected_hosts', {}))}
- Сегментов затронуто: {len(error_summary.get('affected_segments', {}))}
- Пик ошибок: {error_summary.get('time_info', {}).get('peak_time', 'N/A')}

Проанализируй и дай ответ в JSON с полями: root_cause, error_analysis, recommendations (priority/action/command/reason), configuration_changes (parameter/recommended/reason)."""
        
        return prompt