# prompt_builder_gemma.py - Русская версия промптов для Gemma
import json
from datetime import datetime
from typing import Dict, Any


class GemmaPromptBuilder:
    """Формирует промпты на русском языке для Google Gemma"""
    
    SYSTEM_PROMPT = """Ты — ведущий администратор баз данных (DBA) Greenplum с 15-летним опытом. 
Твоя задача — проанализировать отчет об ошибках кластера Greenplum и предоставить диагностику на РУССКОМ языке.

ПРАВИЛА АНАЛИЗА:
1. Найди ПЕРВОПРИЧИНУ (root cause), а не просто перечисляй симптомы
2. Если есть OOM + ошибки Interconnect = каскадный сбой из-за падения одного сегмента
3. Проблемы на одном сегменте часто вызваны сбоем железа (память, диск, сеть)
4. Давай КОНКРЕТНЫЕ команды Greenplum для исправления
5. Указывай реальные параметры GUC и их значения
6. Разделяй инфраструктурные проблемы и ошибки в запросах

ФОРМАТ ОТВЕТА (строго JSON, все поля на русском):
```json
{
  "первопричина": "краткое описание первопричины (1-2 предложения)",
  "анализ": "детальный анализ цепочки событий (3-5 предложений)",
  "затронутые_компоненты": ["компонент1", "компонент2"],
  "рекомендации": [
    {
      "приоритет": "критический/высокий/средний/низкий",
      "действие": "что нужно сделать",
      "команда": "точная команда для выполнения",
      "обоснование": "почему это нужно сделать"
    }
  ],
  "изменения_конфигурации": [
    {
      "параметр": "имя параметра GUC",
      "текущее_предположительно": "предполагаемое текущее значение",
      "рекомендуемое": "рекомендуемое значение",
      "обоснование": "почему это изменение необходимо"
    }
  ],
  "профилактика": ["совет1", "совет2"]
}
```"""

    def build_prompt(self, error_summary: Dict[str, Any]) -> str:
        """Создает структурированный промпт на русском"""
        
        sections = []
        
        sections.append("<отчет_об_ошибках>")
        sections.append(f"Всего ошибок: {error_summary.get('total_errors', 0)}")
        
        # Время
        time_info = error_summary.get('time_info', {})
        if time_info:
            sections.append(f"Период: {time_info.get('first_error', '?')} — {time_info.get('last_error', '?')}")
        
        # Severity
        severity = error_summary.get('severity_distribution', {})
        if severity:
            sev_parts = []
            sev_names = {
                'PANIC': 'ПАНИКА',
                'FATAL': 'КРИТИЧЕСКАЯ',
                'ERROR': 'ОШИБКА',
                'WARNING': 'ПРЕДУПРЕЖДЕНИЕ'
            }
            for sev, count in severity.items():
                sev_name = sev_names.get(sev, sev)
                sev_parts.append(f"{sev_name}={count}")
            sections.append(f"Уровни серьезности: {', '.join(sev_parts)}")
        
        # Типы ошибок
        error_types = error_summary.get('error_types', {})
        if error_types:
            sections.append("\nТипы ошибок:")
            
            # Переводим названия типов
            type_names = {
                'OUT_OF_MEMORY': 'НЕХВАТКА ПАМЯТИ',
                'QUERY_ERROR': 'ОШИБКА ЗАПРОСА',
                'DUPLICATE_KEY': 'ДУБЛИКАТ КЛЮЧА',
                'DATA_ERROR': 'ОШИБКА ДАННЫХ',
                'PANIC': 'ПАНИКА',
                'SIGNAL_ERROR': 'ОШИБКА СИГНАЛА',
                'INTERCONNECT_ERROR': 'ОШИБКА INTERCONNECT',
                'DEADLOCK': 'ВЗАИМНАЯ БЛОКИРОВКА',
                'DISK_ERROR': 'ОШИБКА ДИСКА',
                'CONNECTION_ERROR': 'ОШИБКА ПОДКЛЮЧЕНИЯ',
                'REPLICATION_ERROR': 'ОШИБКА РЕПЛИКАЦИИ',
            }
            
            for etype, info in error_types.items():
                type_name = type_names.get(etype, etype)
                hosts = ', '.join(info.get('hosts', ['неизвестно'])[:2])
                segments = ', '.join(info.get('segments', ['неизвестно'])[:2])
                sections.append(f"  [{info.get('count', 0)}x] {type_name}")
                sections.append(f"    Хосты: {hosts}")
                sections.append(f"    Сегменты: {segments}")
                
                examples = info.get('examples', [])
                for ex in examples[:1]:
                    msg = ex.get('message', '')[:150]
                    detail = ex.get('detail', '')[:100]
                    sections.append(f"    Пример: {msg}")
                    if detail:
                        sections.append(f"    Детали: {detail}")
                    if ex.get('query'):
                        sections.append(f"    Запрос: {ex.get('query', '')[:100]}")
        
        # Критические события
        critical = error_summary.get('critical_events', [])
        if critical:
            sections.append("\nКритические события (PANIC/FATAL):")
            for ev in critical[:5]:
                sections.append(f"  [{ev.get('severity')}] Хост: {ev.get('host')}, Сегмент: {ev.get('segment')}")
                sections.append(f"  Сообщение: {ev.get('message', '')[:150]}")
                if ev.get('detail'):
                    sections.append(f"  Детали: {ev.get('detail', '')[:100]}")
        
        # Системный контекст
        sections.append(f"\nЗатронуто хостов: {len(error_summary.get('affected_hosts', []))}")
        sections.append(f"Затронуто сегментов: {len(error_summary.get('affected_segments', []))}")
        sections.append(f"Базы данных: {', '.join(error_summary.get('databases', ['неизвестно']))}")
        
        sections.append("</отчет_об_ошибках>")
        sections.append("\nПроанализируй отчет и предоставь диагностику на РУССКОМ языке в формате JSON.")
        
        return '\n'.join(sections)