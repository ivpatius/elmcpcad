"""
CLI для работы с электрическими схемами
"""

import asyncio
import json
import click

from electro_cad_ai.core.schematic_analyzer import SchematicAnalyzer, CircuitSynthesizer
from electro_cad_ai.core.block_extractor import BlockExtractor, SmartBlockExtractor
from electro_cad_ai.blocks.library import ElectroBlockLibrary, ElectroBlock, BlockAssembler
from electro_cad_ai.ai.circuit_generator import CircuitAIGenerator
from electro_cad_ai.ai.ollama_client import OllamaClient


def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


@click.group()
@click.option('--library', '-l', default='./electro_library', help='Путь к библиотеке')
@click.pass_context
def cli(ctx, library):
    """ElectroCAD AI - Управление электрическими схемами"""
    ctx.ensure_object(dict)
    ctx.obj['library'] = ElectroBlockLibrary(library)
    ctx.obj['ollama'] = OllamaClient()


@cli.command()
@click.argument('name')
@click.option('--from-dxf', type=click.Path(exists=True), help='Извлечь из DXF')
@click.option('--from-autocad', is_flag=True, help='Извлечь из текущей выборки AutoCAD')
@click.option('--bounds', nargs=4, type=float, help='Границы xmin ymin xmax ymax')
@click.option('--description', '-d', default='', help='Описание блока')
@click.option('--category', '-c', default='extracted',
              type=click.Choice(['power', 'analog', 'digital', 'connectors', 'protection', 'extracted']))
@click.pass_context
def extract(ctx, name, from_dxf, from_autocad, bounds, description, category):
    """Извлечь блок из существующей схемы"""

    if from_dxf:
        from ..core.block_extractor import BlockExtractor
        extractor = BlockExtractor()

        result = extractor.extract_from_dxf(
            from_dxf,
            selection_bounds=bounds,
            block_name=name
        )

        if result:
            block = ElectroBlock(
                name=result["block_name"],
                description=description,
                category=category,
                terminals={"inputs": [], "outputs": [], "power": [], "ground": []},
                geometry=result["geometry"],
                attributes=[],
                bounds=result.get("bounds", {}),
                created_at="",
                updated_at="",
                source="extracted",
                tags=[category],
                dxf_file=result.get("dxf_file")
            )

            saved = ctx.obj['library'].add(block)
            click.echo(f"✓ Блок извлечен и сохранен: {saved}")
        else:
            click.echo("✗ Ошибка извлечения")

    elif from_autocad:
        click.echo("Выберите объекты в AutoCAD и нажмите Enter...")
        input()

        from pyautocad import Autocad
        from ..core.block_extractor import BlockExtractor

        acad = Autocad()
        extractor = BlockExtractor(acad)

        result = extractor.extract_from_selection(name, description=description, category=category)

        if result:
            click.echo(f"✓ Блок создан: {result['block_name']}")

            block = ElectroBlock(
                name=result["block_name"],
                description=description,
                category=category,
                terminals={"inputs": [], "outputs": [], "power": [], "ground": []},
                geometry=result["geometry"],
                attributes=result.get("attributes", []),
                bounds=result.get("bounds", {}),
                created_at="",
                updated_at="",
                source="extracted",
                tags=[category]
            )
            saved = ctx.obj['library'].add(block)
            click.echo(f"💾 Сохранено в библиотеке: {saved}")


@cli.command()
@click.argument('image_path', type=click.Path(exists=True))
@click.option('--category', '-c', default='ai_extracted')
@click.pass_context
def ai_extract(ctx, image_path, category):
    """ИИ анализирует схему и предлагает блоки для извлечения"""

    async def async_extract():
        ollama = ctx.obj['ollama']
        library = ctx.obj['library']

        extractor = SmartBlockExtractor(ollama, None)

        click.echo(f"👁 Анализ схемы: {image_path}")
        suggestions = await extractor.suggest_extractions(image_path)

        click.echo(f"Найдено {len(suggestions)} предложенных блоков:")

        for i, sugg in enumerate(suggestions, 1):
            click.echo(f"\n{i}. {sugg['name']}")
            click.echo(f"   Функция: {sugg.get('function', 'N/A')}")

        for sugg in suggestions:
            block = ElectroBlock(
                name=sugg["name"],
                description=sugg.get("function", ""),
                category=category,
                terminals=sugg.get("terminals", {}),
                geometry=[],
                attributes=[],
                bounds=sugg.get("bounds", {}),
                created_at="",
                updated_at="",
                source="ai_suggested",
                tags=[category, "ai_suggested"],
                extraction_source=image_path
            )
            library.add(block)

        click.echo(f"\n💾 Сохранено {len(suggestions)} блоков")

        await ollama.close()

    loop = get_event_loop()
    loop.run_until_complete(async_extract())


@cli.command()
@click.argument('requirements')
@click.option('--name', '-n', help='Имя схемы')
@click.option('--output', '-o', type=click.Path(), help='Файл для сохранения')
@click.option('--create-in-autocad', is_flag=True, help='Создать в AutoCAD')
@click.pass_context
def generate(ctx, requirements, name, output, create_in_autocad):
    """Сгенерировать схему из требований через ИИ"""

    async def async_generate():
        ollama = ctx.obj['ollama']
        library = ctx.obj['library']

        generator = CircuitAIGenerator(ollama, library)

        click.echo(f"🤖 Генерация схемы: {requirements}")
        click.echo(f"Доступно блоков: {len(library.blocks)}")

        circuit = await generator.generate_from_requirements(
            requirements,
            constraints={"output_name": name} if name else None
        )

        if "error" in circuit:
            click.echo(f"❌ Ошибка: {circuit['error']}")
            return

        click.echo(f"✓ Сгенерирована схема: {circuit.get('circuit_name', 'Untitled')}")
        click.echo(f"  Блоков: {len(circuit.get('blocks', []))}")

        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(circuit, f, indent=2, ensure_ascii=False)
            click.echo(f"💾 Схема сохранена: {output}")

        if create_in_autocad:
            from ..cad.autocad_client import AutoCADClient
            cad = AutoCADClient()

            for block_data in circuit.get("blocks", []):
                block_def = library.get(block_data["block_name"])
                if block_def:
                    cad.create_block(block_def.__dict__ if hasattr(block_def, '__dict__') else block_def)
                    cad.insert_block(
                        block_data["block_name"],
                        block_data["position"],
                        rotation=block_data.get("rotation", 0)
                    )

            click.echo("✓ Схема создана в AutoCAD")

        await ollama.close()

    loop = get_event_loop()
    loop.run_until_complete(async_generate())


@cli.command()
@click.argument('circuit_file', type=click.Path(exists=True))
@click.option('--modification', '-m', required=True, help='Требуемые изменения')
@click.option('--output', '-o', type=click.Path(), help='Файл для сохранения')
@click.pass_context
def modify(ctx, circuit_file, modification, output):
    """Модифицировать существующую схему через ИИ"""

    async def async_modify():
        with open(circuit_file, 'r', encoding='utf-8') as f:
            current_circuit = json.load(f)

        ollama = ctx.obj['ollama']
        library = ctx.obj['library']
        generator = CircuitAIGenerator(ollama, library)

        click.echo(f"🔧 Модификация: {modification}")

        modified = await generator.modify_circuit(current_circuit, modification)

        if "error" not in modified:
            out_path = output or circuit_file.replace('.json', '_modified.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(modified, f, indent=2, ensure_ascii=False)
            click.echo(f"✓ Схема модифицирована: {out_path}")

        await ollama.close()

    loop = get_event_loop()
    loop.run_until_complete(async_modify())


@cli.command()
@click.pass_context
def list_blocks(ctx):
    """Список блоков в библиотеке"""
    library = ctx.obj['library']
    blocks = library.list_blocks()

    if not blocks:
        click.echo("Библиотека пуста")
        return

    click.echo(f"{'Имя':<25} {'Категория':<12} {'Источник':<12} {'Описание'}")
    click.echo("-" * 80)

    for block in blocks:
        desc = block.description[:35] + "..." if len(block.description) > 35 else block.description
        click.echo(f"{block.name:<25} {block.category:<12} {block.source:<12} {desc}")


@cli.command()
@click.argument('name')
@click.pass_context
def show_block(ctx, name):
    """Показать детали блока"""
    library = ctx.obj['library']
    block = library.get(name)

    if not block:
        click.echo(f"Блок '{name}' не найден")
        return

    click.echo(f"Имя: {block.name}")
    click.echo(f"Описание: {block.description}")
    click.echo(f"Категория: {block.category}")
    click.echo(f"Источник: {block.source}")
    click.echo(f"Терминалы:")
    for t_type, terminals in block.terminals.items():
        click.echo(f"  {t_type}: {[t['name'] for t in terminals]}")
    click.echo(f"Геометрия: {len(block.geometry)} элементов")
    click.echo(f"Теги: {', '.join(block.tags)}")


@cli.command()
@click.pass_context
def stats(ctx):
    """Статистика библиотеки"""
    library = ctx.obj['library']
    stats = library.get_statistics()

    click.echo(f"Всего блоков: {stats['total']}")
    click.echo("\nПо категориям:")
    for cat, count in stats['by_category'].items():
        click.echo(f"  {cat}: {count}")
    click.echo(f"\nТипов терминалов: {len(stats['terminal_types'])}")


if __name__ == '__main__':
    cli()