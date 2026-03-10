"""
Генерация электрических схем через ИИ
"""

import json
from typing import Dict, Any, List, Optional


class CircuitAIGenerator:
    """ИИ-генератор электрических схем"""

    SYSTEM_PROMPT = """Ты - опытный инженер-электронщик.
Твоя задача - проектировать электрические схемы из готовых функциональных блоков.

Правила:
1. Используй только блоки из предоставленной библиотеки
2. Учитывай электрические характеристики (напряжение, ток, сигналы)
3. Правильно соединяй входы и выходы блоков
4. Добавляй необходимые разъемы и защиту
5. Размещай блоки логично (вход слева, выход справа)

Отвечай строго в JSON формате."""

    def __init__(self, ollama_client, block_library):
        self.ollama = ollama_client
        self.library = block_library

    async def generate_from_requirements(self,
                                          requirements: str,
                                          constraints: Optional[Dict] = None) -> Dict[str, Any]:
        """Сгенерировать схему из требований"""
        available_blocks = self.library.export_for_ai()

        prompt = f"""Спроектируй электрическую схему.

ТРЕБОВАНИЯ:
{requirements}

ДОСТУПНЫЕ БЛОКИ:
{json.dumps(available_blocks, indent=2, ensure_ascii=False)}

Ограничения:
- Напряжение питания: {constraints.get('input_voltage', '220V AC') if constraints else '220V AC'}
- Выходное напряжение: {constraints.get('output_voltage', '5V DC') if constraints else '5V DC'}
- Ток: {constraints.get('current', '2A') if constraints else '2A'}

Создай:
1. Последовательность блоков (от входа к выходу)
2. Электрические соединения между блоками
3. Размещение блоков на схеме
4. Внешние разъемы

JSON ответ:
{{
    "circuit_name": "Power_Supply_5V_2A",
    "description": "Блок питания с защитой",
    "blocks": [
        {{
            "instance_id": "BR1",
            "block_name": "BRIDGE_RECTIFIER",
            "position": [50, 100],
            "rotation": 0,
            "parameters": {{}}
        }},
        {{
            "instance_id": "F1",
            "block_name": "FUSE_2A",
            "position": [20, 100],
            "rotation": 90
        }}
    ],
    "connections": [
        {{
            "from": "J1.AC_L",
            "to": "F1.IN",
            "net_name": "AC_L"
        }},
        {{
            "from": "F1.OUT",
            "to": "BR1.AC1",
            "net_name": "AC_L_FUSED"
        }}
    ],
    "external_connectors": [
        {{
            "name": "J1",
            "type": "power_input",
            "pins": ["AC_L", "AC_N", "PE"],
            "position": [0, 100]
        }},
        {{
            "name": "J2",
            "type": "power_output", 
            "pins": ["VCC", "GND"],
            "position": [300, 100]
        }}
    ],
    "annotations": [
        {{
            "text": "F1: 2A предохранитель",
            "position": [30, 130]
        }}
    ]
}}"""

        result = await self.ollama.generate_text(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.3
        )

        return self._validate_circuit(result)

    async def modify_circuit(self,
                            current_circuit: Dict[str, Any],
                            modification: str) -> Dict[str, Any]:
        """Модифицировать существующую схему"""
        current_json = json.dumps(current_circuit, indent=2, ensure_ascii=False)

        available_blocks = self.library.export_for_ai()

        prompt = f"""Модифицируй электрическую схему.

ТЕКУЩАЯ СХЕМА:
{current_json}

ТРЕБУЕМЫЕ ИЗМЕНЕНИЯ:
{modification}

ДОСТУПНЫЕ ДОПОЛНИТЕЛЬНЫЕ БЛОКИ:
{json.dumps(available_blocks, indent=2, ensure_ascii=False)}

Верни полную обновленную схему в JSON формате."""

        result = await self.ollama.generate_text(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT
        )

        return self._validate_circuit(result)

    async def optimize_layout(self,
                               circuit: Dict[str, Any]) -> Dict[str, Any]:
        """Оптимизировать размещение блоков на схеме"""
        circuit_json = json.dumps(circuit, indent=2, ensure_ascii=False)

        prompt = f"""Оптимизируй размещение блоков на электрической схеме.

Цели:
1. Минимизировать пересечения соединений
2. Разместить блоки логично (вход слева, выход справа)
3. Группировать связанные блоки
4. Оставлять место для подписей

ТЕКУЩАЯ СХЕМА:
{circuit_json}

Верни схему с обновленными координатами position для каждого блока."""

        return await self.ollama.generate_text(
            prompt=prompt,
            system_prompt=self.SYSTEM_PROMPT
        )

    def _validate_circuit(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация и нормализация схемы"""
        if "error" in data:
            return data

        required = ["circuit_name", "blocks", "connections"]
        for field in required:
            if field not in data:
                data[field] = [] if field in ["blocks", "connections"] else "Untitled"

        # Проверяем, что все блоки существуют в библиотеке
        valid_blocks = []
        for block in data.get("blocks", []):
            if self.library.get(block.get("block_name")):
                valid_blocks.append(block)
            else:
                print(f"⚠ Блок '{block.get('block_name')}' не найден в библиотеке")

        data["blocks"] = valid_blocks

        return data

    async def generate_documentation(self, circuit: Dict[str, Any]) -> str:
        """Сгенерировать документацию к схеме"""
        circuit_json = json.dumps(circuit, indent=2, ensure_ascii=False)

        prompt = f"""Создай техническое описание электрической схемы.

СХЕМА:
{circuit_json}

Создай:
1. Назначение схемы
2. Принцип работы (поэтапно)
3. Таблицу соединений
4. Список используемых компонентов
5. Примечания по монтажу и настройке

Формат: Markdown"""

        result = await self.ollama.generate_text(
            prompt=prompt,
            system_prompt="Ты - технический писатель. Пиши четко и по делу.",
            format_json=False
        )

        return result.get("response", "")