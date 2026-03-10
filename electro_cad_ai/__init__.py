"""
ElectroCAD AI - Управление электрическими схемами через ИИ
"""

__version__ = "1.0.0"

from .ai.ollama_client import OllamaClient
from .blocks.library import ElectroBlockLibrary, ElectroBlock
from .ai.circuit_generator import CircuitAIGenerator

__all__ = ['OllamaClient', 'ElectroBlockLibrary', 'ElectroBlock', 'CircuitAIGenerator']