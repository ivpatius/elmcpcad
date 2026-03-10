from setuptools import setup, find_packages

setup(
    name="electro-cad-ai",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "pyautocad>=0.2.0",
        "ezdxf>=1.1.0",
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
        "click>=8.0.0",
        "pillow>=10.0.0",
        "numpy>=1.24.0",
    ],
    entry_points={
        'console_scripts': [
            'electro-cad=electro_cad_ai.cli.commands:cli',  # Исправлено: electro_cad_ai (с underscore)
        ],
    },
    python_requires='>=3.9',
)