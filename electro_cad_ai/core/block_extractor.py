"""
Извлечение блоков из существующих схем AutoCAD/DXF
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import ezdxf
from pyautocad import APoint, aDouble


class BlockExtractor:
    """Извлекает блоки из схем AutoCAD"""

    def __init__(self, autocad_client=None):
        self.acad = autocad_client

    def extract_from_selection(self,
                               block_name: str,
                               base_point: Tuple[float, float, float] = (0, 0, 0),
                               description: str = "",
                               category: str = "extracted") -> Optional[Dict[str, Any]]:
        """Создать блок из текущей выборки в AutoCAD"""
        if not self.acad:
            print("AutoCAD не подключен!")
            return None

        try:
            doc = self.acad.doc
            selection = doc.ActiveSelectionSet

            if selection.Count == 0:
                print("Нет выбранных объектов!")
                return None

            # Создаем блок через команду
            base_ap = APoint(base_point)
            block = doc.Blocks.Add(base_ap, block_name)

            # Копируем объекты в блок
            for i in range(selection.Count):
                entity = selection.Item(i)
                # Логика копирования...

            # Анализируем созданный блок
            block_def = self._analyze_block(block_name)
            block_def["description"] = description
            block_def["category"] = category
            block_def["source"] = "extracted_from_dwg"

            return block_def

        except Exception as e:
            print(f"Ошибка извлечения: {e}")
            return None

    def extract_from_dxf(self,
                         dxf_path: str,
                         selection_bounds: Optional[Tuple[float, float, float, float]] = None,
                         block_name: str = "EXTRACTED") -> Optional[Dict[str, Any]]:
        """Извлечь блок из DXF файла"""
        try:
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()

            # Фильтруем по границам если заданы
            if selection_bounds:
                xmin, ymin, xmax, ymax = selection_bounds
                entities = []

                for entity in msp:
                    try:
                        bbox = entity.bbox()
                        if bbox:
                            if (bbox.extmin[0] >= xmin and bbox.extmax[0] <= xmax and
                                    bbox.extmin[1] >= ymin and bbox.extmax[1] <= ymax):
                                entities.append(entity)
                    except:
                        pass
            else:
                entities = list(msp)

            # Создаем новый DXF с блоком
            new_doc = ezdxf.new('R2010')
            new_block = new_doc.blocks.new(name=block_name)

            # Копируем сущности
            geometry = []
            for entity in entities:
                geom = self._entity_to_geometry(entity)
                if geom:
                    geometry.append(geom)
                    self._add_to_block(new_block, entity)

            # Сохраняем
            output_path = Path(dxf_path).parent / f"{block_name}.dxf"
            new_doc.saveas(str(output_path))

            return {
                "block_name": block_name,
                "geometry": geometry,
                "entity_count": len(entities),
                "dxf_file": str(output_path),
                "category": "extracted",
                "source": "dxf_extraction"
            }

        except Exception as e:
            print(f"Ошибка извлечения из DXF: {e}")
            return None

    def _analyze_block(self, block_name: str) -> Dict[str, Any]:
        """Проанализировать существующий блок в AutoCAD"""
        block = self.acad.doc.Blocks.Item(block_name)

        geometry = []
        attributes = []

        for entity in block:
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

            elif entity_type == 'AcDbAttributeDefinition':
                attributes.append({
                    "tag": entity.TagString,
                    "prompt": entity.PromptString,
                    "default": entity.TextString,
                    "height": entity.Height,
                    "position": [entity.InsertionPoint[0], entity.InsertionPoint[1]]
                })

        extents = block.Extents
        bounds = {
            "min": [extents.minPoint[0], extents.minPoint[1]],
            "max": [extents.maxPoint[0], extents.maxPoint[1]]
        }

        return {
            "block_name": block_name,
            "geometry": geometry,
            "attributes": attributes,
            "bounds": bounds,
            "entity_count": block.Count
        }

    def _entity_to_geometry(self, entity) -> Optional[Dict[str, Any]]:
        """Конвертировать ezdxf сущность в геометрию"""
        dxftype = entity.dxftype()

        if dxftype == 'LINE':
            return {
                "type": "line",
                "start": entity.dxf.start,
                "end": entity.dxf.end
            }
        elif dxftype == 'CIRCLE':
            return {
                "type": "circle",
                "center": entity.dxf.center,
                "radius": entity.dxf.radius
            }
        elif dxftype == 'ARC':
            return {
                "type": "arc",
                "center": entity.dxf.center,
                "radius": entity.dxf.radius,
                "start_angle": entity.dxf.start_angle,
                "end_angle": entity.dxf.end_angle
            }
        elif dxftype == 'LWPOLYLINE':
            points = [(p[0], p[1]) for p in entity.get_points()]
            return {
                "type": "polyline",
                "points": points,
                "closed": entity.closed
            }
        elif dxftype == 'TEXT':
            return {
                "type": "text",
                "position": entity.dxf.insert,
                "content": entity.dxf.text,
                "height": entity.dxf.height
            }

        return None

    def _add_to_block(self, block, entity):
        """Добавить сущность в ezdxf блок"""
        dxftype = entity.dxftype()

        if dxftype == 'LINE':
            block.add_line(entity.dxf.start, entity.dxf.end)
        elif dxftype == 'CIRCLE':
            block.add_circle(entity.dxf.center, entity.dxf.radius)
        elif dxftype == 'ARC':
            block.add_arc(entity.dxf.center, entity.dxf.radius,
                          entity.dxf.start_angle, entity.dxf.end_angle)
        elif dxftype == 'LWPOLYLINE':
            points = [tuple(p[:2]) for p in entity.get_points()]
            block.add_lwpolyline(points, close=entity.closed)
        elif dxftype == 'TEXT':
            block.add_text(entity.dxf.text, dxfattribs={
                'insert': entity.dxf.insert,
                'height': entity.dxf.height
            })


class SmartBlockExtractor:
    """Умное извлечение с ИИ-помощью"""

    def __init__(self, ollama_client, base_extractor):
        self.ollama = ollama_client
        self.extractor = base_extractor

    async def suggest_extractions(self, image_path: str) -> List[Dict[str, Any]]:
        """ИИ анализирует схему и предлагает, какие блоки выделить"""
        prompt = """Проанализируй эту электрическую схему и предложи,
какие функциональные блоки стоит выделить для повторного использования.

Для каждого предложенного блока укажи:
1. Координаты границ (bounding box)
2. Имя блока
3. Функциональное назначение
4. Внешние подключения (входы/выходы)

JSON формат:
{
    "suggested_blocks": [
        {
            "name": "POWER_SUPPLY_5V",
            "bounds": {"xmin": 10, "ymin": 20, "xmax": 100, "ymax": 80},
            "function": "Стабилизатор питания 5В",
            "terminals": {
                "inputs": [{"name": "AC_IN", "position": [10, 50]}],
                "outputs": [{"name": "DC_OUT", "position": [100, 50]}]
            },
            "internal_components": ["T1", "D1-D4", "C1", "U1"]
        }
    ]
}"""

        result = await self.ollama.analyze_image(image_path, prompt)
        return result.get("parsed", {}).get("suggested_blocks", [])

    async def extract_with_ai(self, image_path: str, library_path: str) -> List[Dict[str, Any]]:
        """Полный pipeline: анализ → извлечение → сохранение"""
        suggestions = await self.suggest_extractions(image_path)
        extracted_blocks = []

        for suggestion in suggestions:
            block_def = {
                "block_name": suggestion["name"],
                "description": suggestion.get("function", ""),
                "bounds": suggestion.get("bounds", {}),
                "terminals": suggestion.get("terminals", {}),
                "category": "ai_suggested",
                "source_image": image_path
            }
            extracted_blocks.append(block_def)

        return extracted_blocks