# lmstudio_client.py - Клиент для LM Studio (OpenAI-совместимый API)
import json
import requests
from typing import Dict, Any, Optional


class LMStudioClient:
    """Клиент для LM Studio с OpenAI-совместимым API"""
    
    def __init__(self, base_url: str = "http://localhost:1234/v1", model: str = "gemma-4-12b-qat"):
        self.base_url = base_url
        self.model = model
        self.headers = {
            "Content-Type": "application/json"
        }
    
    def analyze_logs(
        self, 
        system_prompt: str, 
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Отправляет запрос к LM Studio API
        
        Args:
            system_prompt: Системный промпт (роль DBA)
            user_prompt: Пользовательский промпт (данные логов)
            temperature: Креативность (0.1 = точный ответ)
            max_tokens: Максимальная длина ответа
            
        Returns:
            Dict с результатом анализа
        """
        
        payload = {
            "model": self.model,
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
                timeout=120  # Локальные модели могут работать медленно
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # Извлекаем JSON из ответа
                try:
                    # Ищем JSON блок (между фигурными скобками)
                    json_start = content.find('{')
                    json_end = content.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = content[json_start:json_end]
                        parsed = json.loads(json_str)
                        
                        # Проверяем, что это не пустой объект
                        if parsed and len(parsed) > 0:
                            return {
                                'success': True,
                                'analysis': parsed,
                                'raw_response': content,
                                'usage': {
                                    'prompt_tokens': result.get('usage', {}).get('prompt_tokens', 0),
                                    'completion_tokens': result.get('usage', {}).get('completion_tokens', 0),
                                    'total_tokens': result.get('usage', {}).get('total_tokens', 0)
                                }
                            }
                    
                    # Если JSON не найден или пустой - возвращаем текст
                    return {
                        'success': True,
                        'analysis': {'raw_analysis': content},
                        'raw_response': content,
                        'usage': result.get('usage', {})
                    }
                    
                except json.JSONDecodeError as e:
                    return {
                        'success': True,
                        'analysis': {'raw_analysis': content},
                        'raw_response': content,
                        'usage': result.get('usage', {})
                    }
                    
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'Model not found. Check that LM Studio server is running with the correct model.'
                }
            else:
                return {
                    'success': False,
                    'error': f"API Error: {response.status_code}",
                    'details': response.text[:500]
                }
                
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Cannot connect to LM Studio. Make sure the server is running on http://localhost:1234'
            }
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'error': 'Request timeout. Try reducing prompt size or increasing timeout.'
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def test_connection(self) -> Dict[str, Any]:
        """Проверка подключения к LM Studio"""
        try:
            # Пробуем получить список моделей
            response = requests.get(
                f"{self.base_url}/models",
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                models = [m.get('id', 'unknown') for m in data.get('data', [])]
                return {
                    'connected': True,
                    'models': models
                }
            else:
                return {
                    'connected': False,
                    'error': f"Server returned status {response.status_code}"
                }
                
        except requests.exceptions.ConnectionError:
            return {
                'connected': False,
                'error': 'LM Studio server not running. Start it on port 1234.'
            }
        except Exception as e:
            return {
                'connected': False,
                'error': str(e)
            }
    
    def get_model_info(self) -> Optional[Dict]:
        """Получение информации о текущей модели"""
        try:
            response = requests.get(f"{self.base_url}/models", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    return data['data'][0]
        except:
            pass
        return None


# Тестирование клиента
if __name__ == '__main__':
    print("Testing LM Studio connection...")
    client = LMStudioClient()
    
    # Проверка подключения
    status = client.test_connection()
    print(f"Connection: {status}")
    
    if status.get('connected'):
        # Тестовый запрос
        result = client.analyze_logs(
            system_prompt="You are a helpful assistant. Answer in JSON format.",
            user_prompt="Say hello and return {\"greeting\": \"hello\", \"status\": \"ok\"}",
            max_tokens=100
        )
        print(f"\nTest result: {json.dumps(result, indent=2)}")