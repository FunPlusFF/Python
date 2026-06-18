# deepseek_client.py - Клиент для DeepSeek API
import json
import requests
from typing import Dict, Any, Optional


class DeepSeekClient:
    """Клиент для бесплатного API DeepSeek"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def analyze_logs(
        self, 
        system_prompt: str, 
        user_prompt: str,
        model: str = "deepseek-chat",
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Отправляет запрос к DeepSeek API для анализа логов
        
        Args:
            system_prompt: Системный промпт с ролью
            user_prompt: Пользовательский промпт с данными
            model: Модель (deepseek-chat или deepseek-reasoner)
            temperature: Температура (0-2)
            max_tokens: Максимальное количество токенов в ответе
            
        Returns:
            Dict с результатом анализа или ошибкой
        """
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Пробуем распарсить JSON из ответа
                try:
                    # Ищем JSON в ответе (на случай если модель добавила текст)
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        parsed = json.loads(json_str)
                        return {
                            'success': True,
                            'analysis': parsed,
                            'raw_response': content,
                            'usage': result.get('usage', {})
                        }
                    else:
                        # Если JSON не найден, возвращаем как есть
                        return {
                            'success': True,
                            'analysis': {'raw_analysis': content},
                            'raw_response': content,
                            'usage': result.get('usage', {})
                        }
                        
                except json.JSONDecodeError:
                    return {
                        'success': True,
                        'analysis': {'raw_analysis': content},
                        'raw_response': content,
                        'usage': result.get('usage', {})
                    }
            else:
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'details': response.text
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': "Request timeout - попробуйте уменьшить размер промпта"
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f"Network error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }
    
    def test_connection(self) -> bool:
        """Проверка подключения к API"""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers=self.headers,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False