#!/usr/bin/env python3
"""
Пример полного workflow:
1. Загрузка схемы → 2. Извлечение блоков → 3. Генерация новой схемы
"""

import asyncio
import json
from pathlib import Path

# Импорты из пакета
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from electro_cad_ai import OllamaClient, ElectroBlockLibrary, CircuitAIGenerator
from electro_cad_ai.core.schematic_analyzer import SchematicAnalyzer
from electro_cad_ai.core.block_extractor import SmartBlockExtractor
from electro_cad_ai.blocks.library import ElectroBlock


async def main():
    # Инициализация
    ollama = OllamaClient()
    library = ElectroBlockLibrary("./my_electro_lib")

    print("=" * 60)
    print("ЭТАП 1: Анализ существующей схемы и извлечение блоков")
    print("=" * 60)

    # Анализируем фото/скан схемы
    schematic_image = "./source_schematic.jpg"

    if not Path(schematic_image).exists():
        print(f"⚠ Файл {schematic_image} не найден, пропускаем анализ изображения")
        # Создадим тестовые блоки вручную для демонстрации
        test_blocks = [
            {
                "name": "BRIDGE_RECTIFIER",
                "description": "Мостовой выпрямитель",
                "category": "power",
                "terminals": {
                    "inputs": [{"name": "AC1", "type": "ac"}, {"name": "AC2", "type": "ac"}],
                    "outputs": [{"name": "PLUS", "type": "dc_pos"}, {"name": "MINUS", "type": "dc_neg"}]
                }
            },
            {
                "name": "LM7805",
                "description": "Стабилизатор 5В",
                "category": "power",
                "terminals": {
                    "inputs": [{"name": "IN", "type": "dc_pos"}, {"name": "GND", "type": "ground"}],
                    "outputs": [{"name": "OUT", "type": "dc_pos_5v"}]
                }
            },
            {
                "name": "FUSE_2A",
                "description": "Предохранитель 2А",
                "category": "protection",
                "terminals": {
                    "inputs": [{"name": "IN", "type": "fuse_in"}],
                    "outputs": [{"name": "OUT", "type": "fuse_out"}]
                }
            }
        ]

        for block_data in test_blocks:
            block = ElectroBlock(
                name=block_data["name"],
                description=block_data["description"],
                category=block_data["category"],
                terminals=block_data["terminals"],
                geometry=[],
                attributes=[],
                bounds={},
                created_at="",
                updated_at="",
                source="manual",
                tags=["test"]
            )
            saved = library.add(block)
            print(f"✓ Создан тестовый блок: {saved}")
    else:
        analyzer = SchematicAnalyzer(ollama)
        extractor = SmartBlockExtractor(ollama, None)

        # ИИ находит функциональные блоки на схеме
        suggestions = await extractor.suggest_extractions(schematic_image)
        print(f"Найдено {len(suggestions)} функциональных блоков:")

        for sugg in suggestions:
            print(f"\n  📦 {sugg['name']}: {sugg.get('function', 'N/A')}")

            block = ElectroBlock(
                name=sugg["name"],
                description=sugg.get("function", ""),
                category="ai_extracted",
                terminals=sugg.get("terminals", {}),
                geometry=[],
                attributes=[],
                bounds=sugg.get("bounds", {}),
                created_at="",
                updated_at="",
                source="ai_suggested",
                tags=["from_schematic_001"],
                extraction_source=schematic_image
            )
            saved_name = library.add(block)
            print(f"     💾 Сохранено как: {saved_name}")

    print("\n" + "=" * 60)
    print("ЭТАП 2: Генерация новой схемы из блоков")
    print("=" * 60)

    # Теперь используем ИИ для создания новой схемы из наших блоков
    generator = CircuitAIGenerator(ollama, library)

    requirements = """
    Создать блок питания для аудиоусилителя:
    - Вход: 220V AC
    - Выходы: +30V DC (2A), -30V DC (2A), +5V DC (0.5A для индикации)
    - Защита: от КЗ, от перегрева
    - Индикация: светодиоды "Power" и "Fault"
    - Разъемы: входной IEC, выходные клеммы
    """

    print(f"Требования: {requirements}")
    print("Генерация...")

    circuit = await generator.generate_from_requirements(requirements)

    if "error" not in circuit:
        print(f"\n✓ Сгенерирована схема: {circuit['circuit_name']}")
        print(f"  Использовано блоков: {len(circuit['blocks'])}")

        for block in circuit['blocks']:
            print(f"    - {block['instance_id']}: {block['block_name']}")

        # Сохраняем схему
        output_file = "./generated_power_supply.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(circuit, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Схема сохранена: {output_file}")

        # Генерируем документацию
        docs = await generator.generate_documentation(circuit)
        with open("./generated_power_supply.md", 'w', encoding='utf-8') as f:
            f.write(docs)
        print("📝 Документация создана")
    else:
        print(f"✗ Ошибка: {circuit['error']}")

    print("\n" + "=" * 60)
    print("СТАТИСТИКА БИБЛИОТЕКИ")
    print("=" * 60)
    stats = library.get_statistics()
    print(f"Всего блоков: {stats['total']}")
    print(f"По категориям: {stats['by_category']}")

    await ollama.close()
    print("\n✅ Готово!")


if __name__ == "__main__":
    asyncio.run(main())