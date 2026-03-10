"""
Анализ электрических схем через ИИ
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class ComponentType(Enum):
    RESISTOR = "resistor"
    CAPACITOR = "capacitor"
    INDUCTOR = "inductor"
    DIODE = "diode"
    TRANSISTOR = "transistor"
    IC = "integrated_circuit"
    CONNECTOR = "connector"
    SWITCH = "switch"
    RELAY = "relay"
    FUSE = "fuse"
    POWER_SUPPLY = "power_supply"
    GROUND = "ground"
    UNKNOWN = "unknown"


@dataclass
class Component:
    """Электрический компонент"""
    id: str
    type: ComponentType
    symbol: str
    position: Tuple[float, float]
    rotation: float = 0
    value: Optional[str] = None
    designation: Optional[str] = None
    pins: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.pins is None:
            self.pins = []


@dataclass
class Connection:
    """Соединение между компонентами"""
    from_component: str
    from_pin: str
    to_component: str
    to_pin: str
    net_name: Optional[str] = None


@dataclass
class Schematic:
    """Электрическая схема"""
    name: str
    components: List[Component]
    connections: List[Connection]
    sheet_size: Tuple[float, float] = (297, 210)
    title: Optional[str] = None


class SchematicAnalyzer:
    """Анализатор электрических схем"""

    def __init__(self, ollama_client=None):
        self.ollama = ollama_client

    async def analyze_image(self, image_path: str) -> Schematic:
        """Анализ изображения схемы через qwen3-vl"""
        prompt = """Проанализируй эту электрическую схему.

Определи:
1. Все электрические компоненты (резисторы, конденсаторы, микросхемы, разъемы и т.д.)
2. Их позиционные обозначения (R1, C2, U3 и т.д.)
3. Номиналы/значения (10k, 100nF, LM7805 и т.д.)
4. Точки подключения (выводы компонентов)
5. Электрические соединения между компонентами
6. Цепи питания (VCC, GND, +5V, +12V и т.д.)

Ответь строго в JSON:
{
    "components": [
        {
            "id": "R1",
            "type": "resistor|capacitor|diode|ic|connector|...",
            "symbol": "RESISTOR_IEC",
            "position": [x, y],
            "rotation": 0,
            "value": "10k",
            "designation": "R1",
            "pins": [
                {"id": "1", "position": [x1, y1], "type": "input|output|power|ground"},
                {"id": "2", "position": [x2, y2]}
            ]
        }
    ],
    "connections": [
        {
            "from_component": "R1",
            "from_pin": "1",
            "to_component": "C1",
            "to_pin": "1",
            "net_name": "VCC"
        }
    ],
    "nets": ["VCC", "GND", "SIG_IN", "SIG_OUT"],
    "sheet_info": {
        "title": "Название схемы",
        "size": "A4"
    }
}"""

        result = await self.ollama.analyze_image(image_path, prompt)
        data = result.get("parsed", result)

        components = []
        for comp_data in data.get("components", []):
            comp = Component(
                id=comp_data["id"],
                type=ComponentType(comp_data.get("type", "unknown")),
                symbol=comp_data.get("symbol", "UNKNOWN"),
                position=tuple(comp_data.get("position", [0, 0])),
                rotation=comp_data.get("rotation", 0),
                value=comp_data.get("value"),
                designation=comp_data.get("designation"),
                pins=comp_data.get("pins", [])
            )
            components.append(comp)

        connections = []
        for conn_data in data.get("connections", []):
            conn = Connection(
                from_component=conn_data["from_component"],
                from_pin=conn_data["from_pin"],
                to_component=conn_data["to_component"],
                to_pin=conn_data["to_pin"],
                net_name=conn_data.get("net_name")
            )
            connections.append(conn)

        return Schematic(
            name=data.get("sheet_info", {}).get("title", "Untitled"),
            components=components,
            connections=connections
        )

    async def identify_block_candidates(self, image_path: str) -> List[Dict[str, Any]]:
        """Найти на схеме повторяющиеся фрагменты - кандидаты в блоки"""
        prompt = """Проанализируй эту схему и найди функциональные блоки (модули),
которые можно выделить как отдельные блоки для повторного использования.

Ищи:
- Повторяющиеся фрагменты
- Законченные функциональные узлы (усилители, фильтры, стабилизаторы)
- Интерфейсные модули (входные/выходные цепи)

Для каждого блока определи:
- Границы (прямоугольник вокруг блока)
- Входы/выходы (точки подключения к внешней схеме)
- Функциональное назначение
- Рекомендуемое имя блока

JSON ответ:
{
    "functional_blocks": [
        {
            "name": "AMPLIFIER_STAGE",
            "description": "Усилительный каскад на ОУ",
            "bounds": {"xmin": 10, "ymin": 20, "xmax": 100, "ymax": 80},
            "external_pins": [
                {"name": "INPUT", "position": [10, 50], "type": "input"},
                {"name": "OUTPUT", "position": [100, 50], "type": "output"},
                {"name": "VCC", "position": [50, 80], "type": "power"},
                {"name": "GND", "position": [50, 20], "type": "ground"}
            ],
            "internal_components": ["R1", "R2", "C1", "U1"],
            "confidence": 0.95
        }
    ]
}"""

        result = await self.ollama.analyze_image(image_path, prompt)
        return result.get("parsed", {}).get("functional_blocks", [])


class CircuitSynthesizer:
    """Синтез электрических схем из блоков"""

    STANDARD_BLOCKS = {
        "power_supply_5v": {
            "description": "Стабилизатор 5В на LM7805",
            "inputs": ["VIN_7_12V", "GND"],
            "outputs": ["VOUT_5V", "GND"],
            "components": ["U1_LM7805", "C1_100n", "C2_10u", "D1_1N4007"]
        },
        "amplifier_opamp": {
            "description": "Усилитель на ОУ",
            "inputs": ["IN+", "IN-", "VCC", "VEE"],
            "outputs": ["OUT"],
            "components": ["U1_OPAMP", "R1", "R2", "R3"]
        },
        "rc_filter": {
            "description": "RC фильтр низких частот",
            "inputs": ["IN"],
            "outputs": ["OUT"],
            "components": ["R1", "C1"]
        },
        "led_indicator": {
            "description": "Индикатор на светодиоде",
            "inputs": ["CONTROL", "VCC"],
            "outputs": [],
            "components": ["LED1", "R1"]
        }
    }

    def __init__(self, block_library):
        self.library = block_library

    async def generate_circuit(self, requirements: str,
                               constraints: Optional[Dict] = None) -> Schematic:
        """Сгенерировать схему из требований"""
        available_blocks = self.library.export_for_ai()

        prompt = f"""Спроектируй электрическую схему по требованиям:
"{requirements}"

Доступные функциональные блоки:
{json.dumps(available_blocks, indent=2, ensure_ascii=False)}

Создай схему, состоящую из этих блоков. Определи:
1. Какие блоки нужны
2. Как они соединяются между собой
3. Где разместить каждый блок на листе
4. Внешние разъемы/подключения

Ответь в JSON:
{{
    "circuit_name": "Имя схемы",
    "blocks": [
        {{
            "instance_id": "PS1",
            "block_name": "power_supply_5v",
            "position": [50, 100],
            "rotation": 0,
            "parameters": {{"voltage": "5V"}}
        }}
    ],
    "connections": [
        {{
            "from": "PS1.VOUT_5V",
            "to": "AMP1.VCC",
            "net_name": "+5V"
        }}
    ],
    "external_connectors": [
        {{"name": "J1", "type": "power_input", "position": [0, 100]}}
    ]
}}"""

        result = await self.library.ollama.generate_text(prompt)
        return self._build_schematic_from_ai_response(result)

    def _build_schematic_from_ai_response(self, data: Dict) -> Schematic:
        """Построить схему из ответа ИИ"""
        components = []
        connections = []

        for block_data in data.get("blocks", []):
            block_def = self.library.get(block_data["block_name"])
            if block_def:
                comp = Component(
                    id=block_data["instance_id"],
                    type=ComponentType.IC,
                    symbol=block_data["block_name"],
                    position=tuple(block_data["position"]),
                    rotation=block_data.get("rotation", 0),
                    designation=block_data["instance_id"]
                )
                components.append(comp)

        for conn_data in data.get("connections", []):
            from_parts = conn_data["from"].split(".")
            to_parts = conn_data["to"].split(".")

            conn = Connection(
                from_component=from_parts[0],
                from_pin=from_parts[1] if len(from_parts) > 1 else "1",
                to_component=to_parts[0],
                to_pin=to_parts[1] if len(to_parts) > 1 else "1",
                net_name=conn_data.get("net_name")
            )
            connections.append(conn)

        return Schematic(
            name=data.get("circuit_name", "Generated"),
            components=components,
            connections=connections
        )