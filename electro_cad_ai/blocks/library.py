"""
Управление библиотекой электрических блоков
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class ElectroBlock:
    """Электрический блок"""
    name: str
    description: str
    category: str

    terminals: Dict[str, List[Dict]]
    geometry: List[Dict[str, Any]]
    attributes: List[Dict[str, Any]]
    bounds: Dict[str, List[float]]

    created_at: str
    updated_at: str
    source: str
    tags: List[str]

    dxf_file: Optional[str] = None
    preview_image: Optional[str] = None
    ai_prompt: Optional[str] = None
    extraction_source: Optional[str] = None

    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class ElectroBlockLibrary:
    """Библиотека электрических блоков"""

    def __init__(self, library_path: str = "./electro_library"):
        self.path = Path(library_path)
        self.path.mkdir(parents=True, exist_ok=True)

        self.dxf_path = self.path / "dxf"
        self.preview_path = self.path / "preview"
        self.dxf_path.mkdir(exist_ok=True)
        self.preview_path.mkdir(exist_ok=True)

        self.index_file = self.path / "index.json"
        self.blocks: Dict[str, ElectroBlock] = {}
        self._load_index()

    def _load_index(self):
        """Загрузить индекс библиотеки"""
        if self.index_file.exists():
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for name, block_data in data.items():
                    self.blocks[name] = ElectroBlock(**block_data)

    def _save_index(self):
        """Сохранить индекс"""
        data = {name: asdict(block) for name, block in self.blocks.items()}
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add(self, block: ElectroBlock) -> str:
        """Добавить блок в библиотеку"""
        name = block.name
        if name in self.blocks:
            counter = 1
            while f"{name}_{counter}" in self.blocks:
                counter += 1
            name = f"{name}_{counter}"
            block.name = name

        now = datetime.now().isoformat()
        block.created_at = now
        block.updated_at = now

        self.blocks[name] = block
        self._save_index()

        return name

    def get(self, name: str) -> Optional[ElectroBlock]:
        """Получить блок"""
        return self.blocks.get(name)

    def list_blocks(self,
                    category: Optional[str] = None,
                    source: Optional[str] = None,
                    tag: Optional[str] = None) -> List[ElectroBlock]:
        """Список с фильтрацией"""
        result = list(self.blocks.values())

        if category:
            result = [b for b in result if b.category == category]
        if source:
            result = [b for b in result if b.source == source]
        if tag:
            result = [b for b in result if tag in b.tags]

        return result

    def find_by_terminals(self,
                          required_inputs: List[str],
                          required_outputs: List[str]) -> List[ElectroBlock]:
        """Найти блоки по требуемым входам/выходам"""
        matches = []

        for block in self.blocks.values():
            inputs = [t["name"] for t in block.terminals.get("inputs", [])]
            outputs = [t["name"] for t in block.terminals.get("outputs", [])]

            if all(inp in inputs for inp in required_inputs):
                if all(out in outputs for out in required_outputs):
                    matches.append(block)

        return matches

    def search(self, query: str) -> List[ElectroBlock]:
        """Поиск по названию, описанию, тегам"""
        query = query.lower()
        results = []

        for block in self.blocks.values():
            if (query in block.name.lower() or
                query in block.description.lower() or
                any(query in t.lower() for t in block.tags)):
                results.append(block)

        return results

    def get_compatible_blocks(self, block_name: str) -> List[ElectroBlock]:
        """Найти блоки, совместимые с данным (по терминалам)"""
        base_block = self.blocks.get(block_name)
        if not base_block:
            return []

        base_outputs = [t["name"] for t in base_block.terminals.get("outputs", [])]

        compatible = []
        for name, block in self.blocks.items():
            if name == block_name:
                continue

            inputs = [t["name"] for t in block.terminals.get("inputs", [])]

            if any(out in inputs for out in base_outputs):
                compatible.append(block)

        return compatible

    def delete(self, name: str) -> bool:
        """Удалить блок"""
        if name not in self.blocks:
            return False

        block = self.blocks[name]

        if block.dxf_file:
            Path(block.dxf_file).unlink(missing_ok=True)
        if block.preview_image:
            Path(block.preview_image).unlink(missing_ok=True)

        json_file = self.path / f"{name}.json"
        json_file.unlink(missing_ok=True)

        del self.blocks[name]
        self._save_index()
        return True

    def export_for_ai(self) -> List[Dict[str, Any]]:
        """Экспортировать библиотеку в формат для ИИ"""
        export = []
        for block in self.blocks.values():
            export.append({
                "name": block.name,
                "description": block.description,
                "category": block.category,
                "terminals": {
                    "inputs": [t["name"] for t in block.terminals.get("inputs", [])],
                    "outputs": [t["name"] for t in block.terminals.get("outputs", [])],
                    "power": [t["name"] for t in block.terminals.get("power", [])]
                },
                "tags": block.tags
            })
        return export

    def import_from_json(self, json_path: str) -> List[str]:
        """Импорт блоков из JSON файла"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        imported = []
        for block_data in data.get("blocks", []):
            block = ElectroBlock(**block_data)
            name = self.add(block)
            imported.append(name)

        return imported

    def get_statistics(self) -> Dict[str, Any]:
        """Статистика библиотеки"""
        stats = {
            "total": len(self.blocks),
            "by_category": {},
            "by_source": {},
            "terminal_types": set()
        }

        for block in self.blocks.values():
            stats["by_category"][block.category] = \
                stats["by_category"].get(block.category, 0) + 1
            stats["by_source"][block.source] = \
                stats["by_source"].get(block.source, 0) + 1

            for terminal_type, terminals in block.terminals.items():
                for t in terminals:
                    stats["terminal_types"].add(t["name"])

        stats["terminal_types"] = list(stats["terminal_types"])
        return stats


class BlockAssembler:
    """Сборка схем из блоков библиотеки"""

    def __init__(self, library: ElectroBlockLibrary):
        self.library = library

    def create_schematic(self,
                         block_sequence: List[str],
                         layout: str = "horizontal") -> Dict[str, Any]:
        """Создать схему из последовательности блоков"""
        schematic = {
            "name": "Generated_Schematic",
            "blocks": [],
            "connections": [],
            "nets": []
        }

        x, y = 0, 0
        spacing = 100

        prev_outputs = []

        for i, block_name in enumerate(block_sequence):
            block = self.library.get(block_name)
            if not block:
                continue

            if layout == "horizontal":
                position = [x, y]
                x += spacing
            elif layout == "vertical":
                position = [x, y]
                y -= spacing
            else:
                position = [x + (i % 3) * spacing, y - (i // 3) * spacing]

            instance_id = f"{block_name}_{i}"

            schematic["blocks"].append({
                "instance_id": instance_id,
                "block_name": block_name,
                "position": position,
                "rotation": 0
            })

            # Создаем соединения с предыдущим блоком
            if i > 0 and prev_outputs:
                current_inputs = block.terminals.get("inputs", [])

                for prev_out in prev_outputs:
                    for curr_in in current_inputs:
                        if self._terminals_compatible(prev_out, curr_in):
                            schematic["connections"].append({
                                "from": f"{block_sequence[i-1]}_{i-1}.{prev_out['name']}",
                                "to": f"{instance_id}.{curr_in['name']}",
                                "net_name": f"NET_{i}_{prev_out['name']}"
                            })

            prev_outputs = block.terminals.get("outputs", [])

        return schematic

    def _terminals_compatible(self, output: Dict, input: Dict) -> bool:
        """Проверить совместимость терминалов"""
        out_name = output.get("name", "").lower()
        in_name = input.get("name", "").lower()

        compatible_pairs = [
            ("dc_out", "dc_in"),
            ("ac_out", "ac_in"),
            ("sig_out", "sig_in"),
            ("vcc", "vcc"),
            ("gnd", "gnd"),
            ("5v", "5v_in"),
            ("12v", "12v_in"),
        ]

        for pair in compatible_pairs:
            if pair[0] in out_name and pair[1] in in_name:
                return True

        return False