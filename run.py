#!/usr/bin/env python3
"""
Интерактивный запуск ElectroCAD AI
Выбор команд через меню в консоли
"""

import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# Добавляем путь к пакету
sys.path.insert(0, str(Path(__file__).parent))

from electro_cad_ai import OllamaClient, ElectroBlockLibrary, CircuitAIGenerator
from electro_cad_ai.blocks.library import ElectroBlock, BlockAssembler
from electro_cad_ai.cad.autocad_client import AutoCADClient
from electro_cad_ai.core.block_extractor import BlockExtractor, SmartBlockExtractor
from electro_cad_ai.ai.ollama_client import OllamaClient


def print_header(text):
    """Красивый заголовок"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_menu(title, options):
    """Печать меню с опциями"""
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")
    for key, desc in options.items():
        print(f"  [{key}] {desc}")
    print(f"{'─' * 60}")
    print("  [0] Назад / Выход")


def get_input(prompt, default=None):
    """Получить ввод с дефолтным значением"""
    if default:
        result = input(f"{prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"{prompt}: ").strip()


def get_int_input(prompt, min_val=1, max_val=10, default=1):
    """Получить целое число"""
    while True:
        try:
            value = get_input(prompt, str(default))
            num = int(value)
            if min_val <= num <= max_val:
                return num
            print(f"  Введите число от {min_val} до {max_val}")
        except ValueError:
            print("  Нужно ввести число!")


def get_float_input(prompt, default=0.0):
    """Получить float"""
    while True:
        try:
            value = get_input(prompt, str(default))
            return float(value)
        except ValueError:
            print("  Нужно ввести число!")


def confirm(prompt):
    """Подтверждение да/нет"""
    return input(f"{prompt} (y/n): ").strip().lower() in ['y', 'yes', 'д', 'да']


class ElectroCADInteractive:
    """Интерактивный интерфейс ElectroCAD AI"""

    def __init__(self):
        self.library = None
        self.ollama = None
        self.acad = None
        self.running = True
        self.ollama_url = "http://localhost:11434"  # По умолчанию

    def init_library(self):
        """Инициализация библиотеки"""
        if self.library is None:
            path = get_input("Путь к библиотеке", "./electro_library")
            self.library = ElectroBlockLibrary(path)
            print(f"  ✓ Библиотека: {self.library.path.absolute()}")
            stats = self.library.get_statistics()
            print(f"  📦 Блоков: {stats['total']}")

    def configure_ollama(self):
        """Настройка подключения к Ollama"""
        print_header("НАСТРОЙКА OLLAMA")
        print(f"  Текущий URL: {self.ollama_url}")

        new_url = get_input("Введите URL Ollama (Enter - оставить текущий)", self.ollama_url)
        if new_url:
            self.ollama_url = new_url

        # Проверяем доступность
        import httpx
        try:
            response = httpx.get(f"{self.ollama_url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                print(f"\n  ✓ Ollama доступен")
                print(f"  Модели: {', '.join(models) if models else 'нет моделей'}")

                if "qwen3:latest" not in models:
                    print(f"\n  ⚠ Модель qwen3:latest не найдена")
                    print(f"  Выполните: ollama pull qwen3:latest")
                if "qwen3-vl:30b" not in models:
                    print(f"  ⚠ Модель qwen3-vl:30b не найдена")
                    print(f"  Выполните: ollama pull qwen3-vl:30b")
            else:
                print(f"\n  ✗ Ollama ответил с ошибкой: {response.status_code}")
        except Exception as e:
            print(f"\n  ✗ Не удалось подключиться: {e}")
            print(f"  Проверьте:")
            print(f"    1. Запущен ли Ollama (ollama serve)")
            print(f"    2. Правильный ли URL")
            print(f"    3. Нет ли брандмауэра")

        input("\n  Нажмите Enter...")

    async def init_ollama(self):
        """Инициализация Ollama с настроенным URL"""
        if self.ollama is None:
            self.ollama = OllamaClient(base_url=self.ollama_url)
            print(f"  Подключение к: {self.ollama_url}")
            print("  Проверка моделей...")

            try:
                has_text = await self.ollama.check_model(OllamaClient.TEXT_MODEL)
                has_vision = await self.ollama.check_model(OllamaClient.VISION_MODEL)

                print(f"    {OllamaClient.TEXT_MODEL}: {'✓' if has_text else '✗'}")
                print(f"    {OllamaClient.VISION_MODEL}: {'✓' if has_vision else '✗'}")

                if not has_text and not has_vision:
                    print(f"\n  ⚠ Модели не найдены!")
                    print(f"  Выполните:")
                    print(f"    ollama pull qwen3:latest")
                    print(f"    ollama pull qwen3-vl:30b")
                    return False

                return has_text

            except Exception as e:
                print(f"    ✗ Ошибка подключения: {e}")
                return False

        return True
    def init_autocad(self):
        """Инициализация AutoCAD"""
        if self.acad is None:
            try:
                self.acad = AutoCADClient()
                return True
            except Exception as e:
                print(f"  ⚠ AutoCAD не доступен: {e}")
                return False
        return True

    # ==================== МЕНЮ 1: РАБОТА С БЛОКАМИ ====================

    def menu_blocks(self):
        """Меню работы с блоками"""
        options = {
            '1': 'Создать блок вручную',
            '2': 'Извлечь блок из AutoCAD',
            '3': 'Извлечь блок из DXF',
            '4': 'AI анализ изображения схемы',
            '5': 'Список всех блоков',
            '6': 'Показать детали блока',
            '7': 'Удалить блок',
            '8': 'Импорт блоков из JSON',
        }

        while True:
            print_menu("РАБОТА С БЛОКАМИ", options)
            choice = get_input("Выбор", "0")

            if choice == '0':
                return
            elif choice == '1':
                self.create_block_manual()
            elif choice == '2':
                self.extract_from_autocad()
            elif choice == '3':
                self.extract_from_dxf()
            elif choice == '4':
                asyncio.run(self.ai_extract_image())
            elif choice == '5':
                self.list_blocks()
            elif choice == '6':
                self.show_block()
            elif choice == '7':
                self.delete_block()
            elif choice == '8':
                self.import_blocks()
            else:
                print("  Неверный выбор!")

    def create_block_manual(self):
        """Создать блок вручную"""
        print_header("СОЗДАНИЕ БЛОКА ВРУЧНУЮ")
        self.init_library()

        name = get_input("Имя блока (латиницей)")
        if not name:
            print("  ✗ Имя обязательно!")
            return

        description = get_input("Описание")
        category = get_input("Категория (power/analog/digital/protection/filter/indication)", "custom")

        # Терминалы
        print("\n  Настройка терминалов:")
        terminals = {"inputs": [], "outputs": [], "power": [], "ground": []}

        print("  Входы:")
        while True:
            term_name = get_input("    Имя терминала (пусто для завершения)")
            if not term_name:
                break
            terminals["inputs"].append({
                "name": term_name,
                "type": get_input("    Тип (input/output/power/ground)", "input"),
                "position": [0, 0]
            })

        print("  Выходы:")
        while True:
            term_name = get_input("    Имя терминала (пусто для завершения)")
            if not term_name:
                break
            terminals["outputs"].append({
                "name": term_name,
                "type": get_input("    Тип", "output"),
                "position": [50, 0]
            })

        # Создаем блок
        block = ElectroBlock(
            name=name.upper(),
            description=description,
            category=category,
            terminals=terminals,
            geometry=[],  # Пустая геометрия - можно добавить позже
            attributes=[],
            bounds={"min": [0, -20], "max": [60, 20]},
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source="manual",
            tags=[category, "manual"]
        )

        saved = self.library.add(block)
        print(f"\n  ✓ Блок создан: {saved}")

    def extract_from_autocad(self):
        """Извлечь блок из AutoCAD - УПРОЩЕННАЯ ВЕРСИЯ"""
        print_header("ИЗВЛЕЧЕНИЕ ИЗ AUTOCAD")
        self.init_library()

        if not self.init_autocad():
            print("  ✗ AutoCAD не доступен")
            return

        name = get_input("Имя нового блока")
        if not name:
            print("  ✗ Имя обязательно!")
            return

        category = get_input("Категория", "extracted")
        description = get_input("Описание")

        print("\n  ⚠ Выделите объекты в AutoCAD и нажмите Enter...")
        input()

        try:
            # Проверяем выборку
            selection = self.acad.doc.ActiveSelectionSet
            if selection.Count == 0:
                print("  ✗ Нет выбранных объектов!")
                return

            print(f"  Выбрано объектов: {selection.Count}")

            # Создаем блок через API AutoCAD
            from pyautocad import APoint

            base_point = (0, 0, 0)
            acad_block = self.acad.doc.Blocks.Add(APoint(base_point), name.upper())

            # Копируем объекты в блок через Copy
            copied = 0
            for i in range(selection.Count):
                entity = selection.Item(i)
                try:
                    # Пробуем скопировать
                    entity.Copy(acad_block)
                    copied += 1
                except Exception as e:
                    # Если не копируется - пробуем вручную
                    try:
                        self._copy_entity_manual(entity, acad_block)
                        copied += 1
                    except:
                        pass

            print(f"  Скопировано объектов: {copied}")

            # Получаем геометрию для библиотеки
            geometry = self._get_geometry_from_acad_block(acad_block)

            # Сохраняем в библиотеку
            block = ElectroBlock(
                name=name.upper(),
                description=description,
                category=category,
                terminals={"inputs": [], "outputs": [], "power": [], "ground": []},
                geometry=geometry,
                attributes=[],
                bounds=self._calculate_bounds(geometry),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                source="extracted",
                tags=[category, "autocad"]
            )

            saved = self.library.add(block)
            print(f"  ✓ Блок создан в AutoCAD и сохранен: {saved}")
            print(f"    Объектов в выборке: {selection.Count}")
            print(f"    Скопировано: {copied}")
            print(f"    Геометрии в библиотеке: {len(geometry)}")

        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            import traceback
            traceback.print_exc()

    def _copy_entity_manual(self, entity, block):
        """Ручное копирование сущности в блок"""
        entity_type = entity.EntityName

        if entity_type == 'AcDbLine':
            block.AddLine(entity.StartPoint, entity.EndPoint)
        elif entity_type == 'AcDbCircle':
            block.AddCircle(entity.Center, entity.Radius)
        elif entity_type == 'AcDbArc':
            block.AddArc(entity.Center, entity.Radius, entity.StartAngle, entity.EndAngle)
        elif entity_type == 'AcDbText':
            block.AddText(entity.TextString, entity.InsertionPoint, entity.Height)
        elif entity_type == 'AcDbMText':
            block.AddMText(entity.InsertionPoint, entity.Width, entity.TextString)
        elif entity_type == 'AcDbPolyline':
            from pyautocad import aDouble
            points = []
            for i in range(entity.NumberOfVertices):
                point = entity.Coordinate(i)
                points.extend([point[0], point[1], 0])
            new_poly = block.AddPolyline(aDouble(*points))
            new_poly.Closed = entity.Closed

    def _get_geometry_from_acad_block(self, block):
        """Получить геометрию из блока AutoCAD"""
        geometry = []

        for entity in block:
            try:
                entity_type = entity.EntityName

                if entity_type == 'AcDbLine':
                    geometry.append({
                        "type": "line",
                        "start": [entity.StartPoint[0], entity.StartPoint[1]],
                        "end": [entity.EndPoint[0], entity.EndPoint[1]]
                    })
                elif entity_type == 'AcDbCircle':
                    geometry.append({
                        "type": "circle",
                        "center": [entity.Center[0], entity.Center[1]],
                        "radius": entity.Radius
                    })
                elif entity_type == 'AcDbArc':
                    geometry.append({
                        "type": "arc",
                        "center": [entity.Center[0], entity.Center[1]],
                        "radius": entity.Radius,
                        "start_angle": entity.StartAngle,
                        "end_angle": entity.EndAngle
                    })
                elif entity_type == 'AcDbText':
                    geometry.append({
                        "type": "text",
                        "position": [entity.InsertionPoint[0], entity.InsertionPoint[1]],
                        "content": entity.TextString,
                        "height": entity.Height
                    })
                elif entity_type == 'AcDbPolyline':
                    points = []
                    for i in range(entity.NumberOfVertices):
                        point = entity.Coordinate(i)
                        points.append([point[0], point[1]])
                    geometry.append({
                        "type": "polyline",
                        "points": points,
                        "closed": entity.Closed
                    })
            except Exception as e:
                pass  # Пропускаем проблемные сущности

        return geometry

    def _calculate_bounds(self, geometry):
        """Вычислить границы геометрии"""
        if not geometry:
            return {"min": [0, 0], "max": [100, 100]}

        all_x = []
        all_y = []

        for geom in geometry:
            if geom["type"] == "line":
                all_x.extend([geom["start"][0], geom["end"][0]])
                all_y.extend([geom["start"][1], geom["end"][1]])
            elif geom["type"] == "circle":
                all_x.extend([geom["center"][0] - geom["radius"], geom["center"][0] + geom["radius"]])
                all_y.extend([geom["center"][1] - geom["radius"], geom["center"][1] + geom["radius"]])
            elif geom["type"] == "arc":
                all_x.extend([geom["center"][0] - geom["radius"], geom["center"][0] + geom["radius"]])
                all_y.extend([geom["center"][1] - geom["radius"], geom["center"][1] + geom["radius"]])
            elif geom["type"] == "polyline":
                for point in geom["points"]:
                    all_x.append(point[0])
                    all_y.append(point[1])
            elif geom["type"] == "text":
                all_x.append(geom["position"][0])
                all_y.append(geom["position"][1])

        if all_x and all_y:
            return {
                "min": [min(all_x), min(all_y)],
                "max": [max(all_x), max(all_y)]
            }
        return {"min": [0, 0], "max": [100, 100]}

    def extract_from_dxf(self):
        """Извлечь блок из DXF"""
        print_header("ИЗВЛЕЧЕНИЕ ИЗ DXF")
        self.init_library()

        dxf_path = get_input("Путь к DXF файлу")
        if not Path(dxf_path).exists():
            print("  ✗ Файл не найден!")
            return

        name = get_input("Имя блока", Path(dxf_path).stem.upper())
        category = get_input("Категория", "extracted")

        # Границы (опционально)
        use_bounds = confirm("Указать границы выборки?")
        bounds = None
        if use_bounds:
            xmin = get_float_input("  X min", 0)
            ymin = get_float_input("  Y min", 0)
            xmax = get_float_input("  X max", 100)
            ymax = get_float_input("  Y max", 100)
            bounds = (xmin, ymin, xmax, ymax)

        extractor = BlockExtractor()
        result = extractor.extract_from_dxf(dxf_path, bounds, name)

        if result:
            block = ElectroBlock(
                name=result["block_name"],
                description=f"Extracted from {Path(dxf_path).name}",
                category=category,
                terminals={"inputs": [], "outputs": [], "power": [], "ground": []},
                geometry=result["geometry"],
                attributes=[],
                bounds=result.get("bounds", {}),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                source="dxf",
                tags=[category, "dxf"],
                dxf_file=result.get("dxf_file")
            )
            saved = self.library.add(block)
            print(f"  ✓ Извлечено: {saved}")
            print(f"  📁 DXF сохранен: {result.get('dxf_file')}")
        else:
            print("  ✗ Ошибка извлечения")

    async def ai_extract_image(self):
        """AI анализ изображения"""
        print_header("AI АНАЛИЗ ИЗОБРАЖЕНИЯ СХЕМЫ")
        self.init_library()

        if not await self.init_ollama():
            print("  ✗ Ollama недоступен")
            return

        image_path = get_input("Путь к изображению (JPG/PNG)")
        if not Path(image_path).exists():
            print("  ✗ Файл не найден!")
            return

        category = get_input("Категория для новых блоков", "ai_extracted")

        print("  🔍 Анализ изображения через qwen3-vl...")
        extractor = SmartBlockExtractor(self.ollama, None)

        suggestions = await extractor.suggest_extractions(image_path)

        if not suggestions:
            print("  ⚠ Блоки не найдены")
            return

        print(f"\n  Найдено {len(suggestions)} блоков:")
        for i, sugg in enumerate(suggestions, 1):
            print(f"\n  {i}. {sugg['name']}")
            print(f"     Описание: {sugg.get('function', 'N/A')}")
            print(f"     Терминалы: {list(sugg.get('terminals', {}).keys())}")

        # Сохраняем выбранные
        to_save = get_input("Какие сохранить? (все/номера через запятую/0-отмена)", "all")

        if to_save == '0':
            return

        saved_count = 0
        for i, sugg in enumerate(suggestions, 1):
            if to_save == "all" or str(i) in to_save.split(","):
                block = ElectroBlock(
                    name=sugg["name"],
                    description=sugg.get("function", ""),
                    category=category,
                    terminals=sugg.get("terminals", {}),
                    geometry=[],
                    attributes=[],
                    bounds=sugg.get("bounds", {}),
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    source="ai_suggested",
                    tags=[category, "ai_suggested"],
                    extraction_source=image_path
                )
                saved = self.library.add(block)
                print(f"  ✓ Сохранено: {saved}")
                saved_count += 1

        print(f"\n  💾 Всего сохранено: {saved_count} блоков")

    def list_blocks(self):
        """Список блоков"""
        print_header("БЛОКИ В БИБЛИОТЕКЕ")
        self.init_library()

        # Фильтр по категории
        filter_cat = get_input("Фильтр по категории (все/имя категории)", "все")

        if filter_cat == "все":
            blocks = self.library.list_blocks()
        else:
            blocks = self.library.list_blocks(category=filter_cat)

        if not blocks:
            print("  Библиотека пуста")
            return

        print(f"\n  Всего: {len(blocks)} блоков")
        print(f"\n  {'Имя':<25} {'Категория':<12} {'Источник':<12} {'Описание'}")
        print("  " + "-" * 70)

        for block in blocks:
            desc = block.description[:30] + "..." if len(block.description) > 30 else block.description
            print(f"  {block.name:<25} {block.category:<12} {block.source:<12} {desc}")

    def show_block(self):
        """Показать детали блока"""
        print_header("ДЕТАЛИ БЛОКА")
        self.init_library()

        name = get_input("Имя блока")
        block = self.library.get(name)

        if not block:
            print(f"  ✗ Блок '{name}' не найден")
            return

        print(f"\n  Имя: {block.name}")
        print(f"  Описание: {block.description}")
        print(f"  Категория: {block.category}")
        print(f"  Источник: {block.source}")
        print(f"  Теги: {', '.join(block.tags)}")

        print(f"\n  Терминалы:")
        for t_type, terminals in block.terminals.items():
            if terminals:
                print(f"    {t_type}: {', '.join([t['name'] for t in terminals])}")

        print(f"\n  Геометрия: {len(block.geometry)} элементов")
        print(f"  Границы: {block.bounds}")

        if block.dxf_file:
            print(f"  📁 DXF: {block.dxf_file}")

    def delete_block(self):
        """Удалить блок"""
        print_header("УДАЛЕНИЕ БЛОКА")
        self.init_library()

        name = get_input("Имя блока для удаления")
        if not name:
            return

        block = self.library.get(name)
        if not block:
            print(f"  ✗ Блок '{name}' не найден")
            return

        print(f"\n  Будет удален: {name}")
        print(f"  Описание: {block.description}")

        if confirm("Подтвердить удаление?"):
            if self.library.delete(name):
                print(f"  ✓ Блок '{name}' удален")
            else:
                print(f"  ✗ Ошибка удаления")
        else:
            print("  Отменено")

    def import_blocks(self):
        """Импорт из JSON"""
        print_header("ИМПОРТ БЛОКОВ ИЗ JSON")
        self.init_library()

        json_path = get_input("Путь к JSON файлу")
        if not Path(json_path).exists():
            print("  ✗ Файл не найден!")
            return

        try:
            imported = self.library.import_from_json(json_path)
            print(f"  ✓ Импортировано {len(imported)} блоков:")
            for name in imported:
                print(f"    - {name}")
        except Exception as e:
            print(f"  ✗ Ошибка импорта: {e}")

    # ==================== МЕНЮ 2: ГЕНЕРАЦИЯ СХЕМ ====================

    async def menu_circuits(self):
        """Меню генерации схем"""
        options = {
            '1': 'Сгенерировать схему через ИИ (из описания)',
            '2': 'Собрать схему вручную из блоков',
            '3': 'Модифицировать существующую схему',
            '4': 'Создать схему в AutoCAD',
            '5': 'Показать последнюю сгенерированную схему',
        }

        while True:
            print_menu("ГЕНЕРАЦИЯ СХЕМ", options)
            choice = get_input("Выбор", "0")

            if choice == '0':
                return
            elif choice == '1':
                await self.generate_circuit_ai()
            elif choice == '2':
                self.assemble_circuit_manual()
            elif choice == '3':
                await self.modify_circuit()
            elif choice == '4':
                self.create_circuit_in_autocad()
            elif choice == '5':
                self.show_last_circuit()
            else:
                print("  Неверный выбор!")

    async def generate_circuit_ai(self):
        """Генерация схемы через ИИ"""
        print_header("ГЕНЕРАЦИЯ СХЕМЫ ЧЕРЕЗ ИИ")
        self.init_library()

        if not await self.init_ollama():
            print("  ⚠ ИИ недоступен, переключение на ручную сборку")
            self.assemble_circuit_manual()
            return

        # Показываем доступные блоки
        blocks = self.library.list_blocks()
        if not blocks:
            print("  ⚠ Библиотека пуста! Сначала создайте блоки.")
            return

        print(f"\n  Доступно блоков: {len(blocks)}")
        print("  " + ", ".join([b.name for b in blocks[:5]]) + ("..." if len(blocks) > 5 else ""))

        # Требования
        print("\n  Введите требования к схеме (например):")
        print('    "Блок питания 5В 2А с защитой от КЗ и индикацией"')
        print('    "Усилитель звука 50Вт на TDA2030 с регулятором громкости"')
        print('    "Фильтр низких частот для сабвуфера, частота среза 100Гц"')

        requirements = get_input("\n  Требования")
        if not requirements:
            return

        name = get_input("  Имя схемы", "Generated_Circuit")
        save_path = get_input("  Сохранить в файл", f"./{name}.json")

        print(f"\n  🤖 Генерация схемы...")
        print(f"  Требования: {requirements[:60]}...")

        generator = CircuitAIGenerator(self.ollama, self.library)

        try:
            circuit = await generator.generate_from_requirements(
                requirements,
                constraints={"output_name": name}
            )

            if "error" in circuit:
                print(f"  ✗ Ошибка ИИ: {circuit['error']}")
                if confirm("Попробовать ручную сборку?"):
                    self.assemble_circuit_manual()
                return

            print(f"\n  ✓ Сгенерирована схема: {circuit.get('circuit_name', name)}")
            print(f"    Блоков: {len(circuit.get('blocks', []))}")
            print(f"    Соединений: {len(circuit.get('connections', []))}")

            for block in circuit.get('blocks', []):
                print(f"    - {block.get('instance_id')}: {block.get('block_name')}")

            # Сохраняем
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(circuit, f, indent=2, ensure_ascii=False)
            print(f"  💾 Сохранено: {save_path}")

            # Документация
            if confirm("Сгенерировать документацию?"):
                docs = await generator.generate_documentation(circuit)
                doc_path = save_path.replace('.json', '.md')
                with open(doc_path, 'w', encoding='utf-8') as f:
                    f.write(docs)
                print(f"  📝 Документация: {doc_path}")

            # Создание в AutoCAD
            if confirm("Создать в AutoCAD?"):
                self.create_circuit_in_autocad_from_data(circuit)

        except Exception as e:
            print(f"  ✗ Ошибка: {e}")
            import traceback
            traceback.print_exc()

    def assemble_circuit_manual(self):
        """Ручная сборка схемы из блоков"""
        print_header("РУЧНАЯ СБОРКА СХЕМЫ")
        self.init_library()

        blocks = self.library.list_blocks()
        if not blocks:
            print("  ⚠ Нет блоков в библиотеке!")
            return

        # Показываем блоки с номерами
        print("\n  Доступные блоки:")
        for i, block in enumerate(blocks, 1):
            print(f"    {i}. {block.name} ({block.category}) - {block.description[:40]}...")

        # Выбор последовательности
        print("\n  Введите номера блоков в порядке соединения (через запятую)")
        print("  Например: 3,1,2,4")

        sequence_str = get_input("  Последовательность")
        try:
            indices = [int(x.strip()) - 1 for x in sequence_str.split(",")]
            sequence = [blocks[i].name for i in indices if 0 <= i < len(blocks)]
        except:
            print("  ✗ Неверный формат")
            return

        if not sequence:
            print("  ✗ Не выбраны блоки")
            return

        print(f"\n  Выбрана последовательность: {' → '.join(sequence)}")

        # Размещение
        layout = get_input("  Размещение (horizontal/vertical/grid)", "horizontal")

        assembler = BlockAssembler(self.library)
        circuit = assembler.create_schematic(sequence, layout)

        circuit["circuit_name"] = get_input("  Имя схемы", "Manual_Assembly")
        circuit["description"] = get_input("  Описание", "Собрано вручную")

        # Внешние разъемы
        if confirm("Добавить внешние разъемы?"):
            connectors = []
            while True:
                conn_name = get_input("    Имя разъема (пусто для завершения)")
                if not conn_name:
                    break
                conn_type = get_input("    Тип (power_input/signal_input/output)", "power_input")
                connectors.append({
                    "name": conn_name,
                    "type": conn_type,
                    "pins": [],
                    "position": [0, 0]
                })
            circuit["external_connectors"] = connectors

        # Сохранение
        save_path = get_input("  Сохранить в файл", f"./{circuit['circuit_name']}.json")
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(circuit, f, indent=2, ensure_ascii=False)

        print(f"\n  ✓ Схема собрана и сохранена: {save_path}")
        print(f"    Блоков: {len(circuit['blocks'])}")
        print(f"    Соединений: {len(circuit['connections'])}")

    async def modify_circuit(self):
        """Модификация схемы"""
        print_header("МОДИФИКАЦИЯ СХЕМЫ")

        json_path = get_input("Путь к JSON файлу схемы")
        if not Path(json_path).exists():
            print("  ✗ Файл не найден!")
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            circuit = json.load(f)

        print(f"\n  Загружена схема: {circuit.get('circuit_name', 'Unknown')}")
        print(f"  Текущих блоков: {len(circuit.get('blocks', []))}")

        print("\n  Что нужно изменить? Например:")
        print('    "Добавь индикацию перегрузки"')
        print('    "Увеличь ток до 5А и добавь радиатор"')
        print('    "Замени стабилизатор на импульсный"')

        modification = get_input("\n  Модификация")
        if not modification:
            return

        if not await self.init_ollama():
            print("  ✗ ИИ недоступен для модификации")
            return

        self.init_library()
        generator = CircuitAIGenerator(self.ollama, self.library)

        print("\n  🔧 Модификация...")
        try:
            modified = await generator.modify_circuit(circuit, modification)

            if "error" in modified:
                print(f"  ✗ Ошибка: {modified['error']}")
                return

            new_name = circuit.get('circuit_name', 'Modified') + '_v2'
            save_path = get_input("  Сохранить как", f"./{new_name}.json")

            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(modified, f, indent=2, ensure_ascii=False)

            print(f"\n  ✓ Схема модифицирована: {save_path}")
            print(f"    Было блоков: {len(circuit.get('blocks', []))}")
            print(f"    Стало блоков: {len(modified.get('blocks', []))}")

        except Exception as e:
            print(f"  ✗ Ошибка: {e}")

    def create_circuit_in_autocad(self):
        """Создать схему в AutoCAD из файла"""
        print_header("СОЗДАНИЕ СХЕМЫ В AUTOCAD")

        json_path = get_input("Путь к JSON файлу схемы")
        if not Path(json_path).exists():
            print("  ✗ Файл не найден!")
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            circuit = json.load(f)

        self.create_circuit_in_autocad_from_data(circuit)

    def create_circuit_in_autocad_from_data(self, circuit: dict):
        """Создание в AutoCAD из данных схемы"""
        if not self.init_autocad():
            return

        print(f"\n  Создание схемы: {circuit.get('circuit_name', 'Unknown')}")
        print(f"  Блоков для создания: {len(circuit.get('blocks', []))}")

        # Создаем определения блоков
        created_blocks = []
        for block_data in circuit.get('blocks', []):
            block_name = block_data['block_name']
            block_def = self.library.get(block_name)

            if block_def:
                # Конвертируем в dict
                if hasattr(block_def, '__dict__'):
                    block_dict = block_def.__dict__
                else:
                    block_dict = block_def

                success = self.acad.create_block(block_dict)
                if success:
                    created_blocks.append(block_name)
                    print(f"    ✓ Блок '{block_name}' создан")
            else:
                print(f"    ⚠ Блок '{block_name}' не найден в библиотеке")

        # Вставляем экземпляры
        print("\n  Вставка блоков...")
        for i, block_data in enumerate(circuit.get('blocks', [])):
            block_name = block_data['block_name']
            position = block_data.get('position', [i * 100, 0, 0])
            rotation = block_data.get('rotation', 0)

            success = self.acad.insert_block(block_name, tuple(position), rotation=rotation)
            if success:
                print(f"    ✓ {block_data.get('instance_id', block_name)} в {position}")

        print(f"\n  ✅ Схема создана в AutoCAD!")
        print(f"    Создано блоков: {len(created_blocks)}")

    def show_last_circuit(self):
        """Показать последнюю схему"""
        print_header("ПОСЛЕДНЯЯ СХЕМА")

        # Ищем последний JSON файл
        json_files = sorted(Path('.').glob('*.json'), key=lambda x: x.stat().st_mtime, reverse=True)

        circuit_files = [f for f in json_files if
                         'circuit' in f.name.lower() or 'generated' in f.name.lower() or 'manual' in f.name.lower()]

        if not circuit_files:
            print("  Не найдены файлы схем")
            return

        last_file = circuit_files[0]
        print(f"  Последняя схема: {last_file}")

        with open(last_file, 'r', encoding='utf-8') as f:
            circuit = json.load(f)

        print(f"\n  Название: {circuit.get('circuit_name', 'Unknown')}")
        print(f"  Описание: {circuit.get('description', 'Нет описания')}")
        print(f"\n  Блоки ({len(circuit.get('blocks', []))}):")
        for block in circuit.get('blocks', []):
            print(f"    - {block.get('instance_id')}: {block.get('block_name')} at {block.get('position')}")

        print(f"\n  Соединения ({len(circuit.get('connections', []))}):")
        for conn in circuit.get('connections', [])[:5]:  # Первые 5
            print(f"    {conn.get('from')} → {conn.get('to')} ({conn.get('net_name', 'N/A')})")
        if len(circuit.get('connections', [])) > 5:
            print(f"    ... и еще {len(circuit.get('connections', [])) - 5}")

    # ==================== МЕНЮ 3: СТАТИСТИКА И НАСТРОЙКИ ====================

    def menu_stats(self):
        """Меню статистики"""
        print_header("СТАТИСТИКА И НАСТРОЙКИ")
        self.init_library()

        stats = self.library.get_statistics()

        print(f"\n  📦 Всего блоков: {stats['total']}")

        print(f"\n  По категориям:")
        for cat, count in sorted(stats['by_category'].items(), key=lambda x: x[1], reverse=True):
            print(f"    {cat}: {count}")

        print(f"\n  По источникам:")
        for src, count in sorted(stats['by_source'].items(), key=lambda x: x[1], reverse=True):
            print(f"    {src}: {count}")

        print(f"\n  Типов терминалов: {len(stats.get('terminal_types', []))}")
        if len(stats.get('terminal_types', [])) > 0:
            print(f"    {', '.join(stats['terminal_types'][:10])}")

        input("\n  Нажмите Enter для продолжения...")

    # ==================== ГЛАВНОЕ МЕНЮ ====================

    def main_menu(self):
        """Главное меню"""
        options = {
            '1': 'Работа с блоками (создание, извлечение, просмотр)',
            '2': 'Генерация схем (ИИ, ручная сборка)',
            '3': 'Статистика и настройки',
        }

        while self.running:
            print_header("ElectroCAD AI - Главное меню")

            if self.library:
                stats = self.library.get_statistics()
                print(f"  📦 Блоков в библиотеке: {stats['total']}")

            print_menu("ВЫБЕРИТЕ РАЗДЕЛ", options)

            choice = get_input("Выбор")

            if choice == '0':
                self.running = False
                print("\n  👋 До свидания!")
            elif choice == '1':
                self.menu_blocks()
            elif choice == '2':
                asyncio.run(self.menu_circuits())
            elif choice == '3':
                self.menu_stats()
            else:
                print("  Неверный выбор!")

    def run(self):
        """Запуск интерфейса"""
        try:
            self.main_menu()
        except KeyboardInterrupt:
            print("\n\n  👋 Прервано пользователем")
        finally:
            if self.ollama:
                asyncio.run(self.ollama.close())


def main():
    """Точка входа"""
    app = ElectroCADInteractive()
    app.run()


if __name__ == "__main__":
    main()