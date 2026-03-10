"""
Клиент для работы с AutoCAD
"""

from typing import Dict, Any, List, Tuple, Optional, Union

from pyautocad import Autocad, APoint, aDouble


class AutoCADClient:
    """Клиент для работы с AutoCAD"""

    def __init__(self):
        self.acad = None
        self.doc = None
        self.model = None
        self._connect()

    def _connect(self):
        """Подключиться к AutoCAD"""
        try:
            self.acad = Autocad(create_if_not_exists=True)
            self.doc = self.acad.doc
            self.model = self.acad.model
            print(f"✓ Подключено к AutoCAD: {self.doc.Name}")
        except Exception as e:
            print(f"⚠ Не удалось подключиться к AutoCAD: {e}")
            raise ConnectionError(f"AutoCAD не доступен: {e}")

    def create_block(self, block_def: Dict[str, Any]) -> bool:
        """Создать блок в AutoCAD из определения"""
        try:
            name = block_def["block_name"]
            base_point = APoint(block_def.get("base_point", [0, 0, 0]))

            # Проверяем существование
            try:
                existing = self.doc.Blocks.Item(name)
                print(f"Блок '{name}' уже существует!")
                return False
            except:
                pass

            # Создаем блок
            block = self.doc.Blocks.Add(base_point, name)

            # Добавляем геометрию
            for geom in block_def.get("geometry", []):
                self._add_geometry_to_block(block, geom)

            # Добавляем атрибуты
            for attr in block_def.get("attributes", []):
                self._add_attribute_to_block(block, attr, base_point)

            print(f"✓ Блок '{name}' создан в AutoCAD")
            return True

        except Exception as e:
            print(f"✗ Ошибка создания блока: {e}")
            return False

    def insert_block(self,
                     name: str,
                     position: Tuple[float, float, float],
                     scale: Union[float, Tuple[float, float, float]] = 1.0,
                     rotation: float = 0.0,
                     attributes: Optional[Dict[str, str]] = None) -> bool:
        """Вставить блок в чертеж"""
        try:
            if isinstance(scale, (int, float)):
                xscale = yscale = zscale = float(scale)
            else:
                xscale, yscale, zscale = map(float, scale)

            insert_point = APoint(position)

            block_ref = self.model.InsertBlock(
                insert_point, name, xscale, yscale, zscale, rotation
            )

            # Устанавливаем атрибуты
            if attributes and block_ref.HasAttributes:
                for attr_ref in block_ref.GetAttributes():
                    tag = attr_ref.TagString
                    if tag in attributes:
                        attr_ref.TextString = attributes[tag]

            print(f"✓ Блок '{name}' вставлен в {position}")
            return True

        except Exception as e:
            print(f"✗ Ошибка вставки блока: {e}")
            return False

    def create_and_insert(self,
                          block_def: Dict[str, Any],
                          position: Optional[Tuple[float, float, float]] = None,
                          attributes: Optional[Dict[str, str]] = None) -> bool:
        """Создать блок и сразу вставить его"""
        success = self.create_block(block_def)
        if not success:
            return False

        if position is None:
            position = (0, 0, 0)

        # Используем атрибуты из определения если не указаны
        if attributes is None:
            attributes = {}
            for attr in block_def.get("attributes", []):
                tag = attr.get("tag", "")
                default = attr.get("default", "")
                if tag:
                    attributes[tag] = default

        return self.insert_block(
            block_def["block_name"],
            position,
            attributes=attributes
        )

    def _add_geometry_to_block(self, block, geom: Dict[str, Any]):
        """Добавить геометрию в блок"""
        geom_type = geom.get("type", "").lower()

        if geom_type == "line":
            start = APoint(geom["start"])
            end = APoint(geom["end"])
            block.AddLine(start, end)

        elif geom_type == "circle":
            center = APoint(geom["center"])
            radius = float(geom["radius"])
            block.AddCircle(center, radius)

        elif geom_type == "arc":
            center = APoint(geom["center"])
            radius = float(geom["radius"])
            start_angle = float(geom.get("start_angle", 0))
            end_angle = float(geom.get("end_angle", 90))
            block.AddArc(center, radius, start_angle, end_angle)

        elif geom_type == "polyline":
            points = geom.get("points", [])
            if points:
                coords = []
                for p in points:
                    coords.extend([float(p[0]), float(p[1]), 0.0])

                pl = block.AddPolyline(aDouble(*coords))
                if geom.get("closed", False):
                    pl.Closed = True

        elif geom_type == "text":
            position = APoint(geom["position"])
            text = str(geom["content"])
            height = float(geom.get("height", 2.5))
            block.AddText(text, position, height)

    def _add_attribute_to_block(self, block, attr: Dict[str, Any], base_point):
        """Добавить атрибут в блок"""
        tag = str(attr.get("tag", "ATTR")).upper()
        prompt = str(attr.get("prompt", tag))
        default = str(attr.get("default", ""))
        height = float(attr.get("height", 2.5))

        attr_pos = attr.get("position", [0, 0, 0])
        insert_point = APoint(
            base_point[0] + attr_pos[0],
            base_point[1] + attr_pos[1],
            base_point[2] + attr_pos[2]
        )

        block.AddAttribute(height, 0, prompt, insert_point, tag, default)

    def block_exists(self, name: str) -> bool:
        """Проверить существование блока"""
        try:
            self.doc.Blocks.Item(name)
            return True
        except:
            return False

    def get_block_names(self) -> list:
        """Получить список блоков в чертеже"""
        names = []
        for i in range(self.doc.Blocks.Count):
            block = self.doc.Blocks.Item(i)
            if not block.IsAnonymous and not block.IsLayout:
                names.append(block.Name)
        return names

    def import_dxf_to_autocad(self, dxf_path: str) -> bool:
        """Импортировать DXF файл в текущий чертеж"""
        try:
            self.doc.SendCommand(f'_.INSERT "{dxf_path}" 0,0 1 1 0 \n')
            return True
        except Exception as e:
            print(f"Ошибка импорта DXF: {e}")
            return False