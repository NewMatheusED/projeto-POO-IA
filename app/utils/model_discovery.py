"""
Sistema de descoberta automática de modelos.
Descobre e importa todos os modelos do projeto automaticamente.
"""

import importlib
import inspect
import os
from typing import Dict, List, Type

from app.database import db


class ModelDiscovery:
    """
    Classe responsável por descobrir e importar automaticamente todos os modelos.
    Segue o princípio de responsabilidade única (SRP) e é extensível (OCP).
    """

    def __init__(self, app_root: str = None):
        """
        Inicializa o descobridor de modelos.

        Args:
            app_root: Caminho raiz da aplicação (padrão: diretório atual)
        """
        self.app_root = app_root or os.path.dirname(os.path.dirname(__file__))
        self.discovered_models: Dict[str, Type] = {}

    def discover_models(self) -> Dict[str, Type]:
        """
        Descobre todos os modelos do projeto automaticamente.

        Returns:
            Dicionário com nome do modelo e classe do modelo
        """
        print("🔍 Descobrindo modelos automaticamente...")

        # Limpar cache de modelos descobertos
        self.discovered_models.clear()

        # Buscar em todas as pastas de serviços
        services_path = os.path.join(self.app_root, "services")
        if os.path.exists(services_path):
            self._discover_in_directory(services_path)

        # Buscar na pasta de modelos base
        models_path = os.path.join(self.app_root, "models")
        if os.path.exists(models_path):
            self._discover_in_directory(models_path)

        # Buscar em outras pastas que possam conter modelos
        other_paths = ["auth", "webhooks"]
        for path_name in other_paths:
            path = os.path.join(self.app_root, path_name)
            if os.path.exists(path):
                self._discover_in_directory(path)

        print(f"✅ {len(self.discovered_models)} modelos descobertos: {list(self.discovered_models.keys())}")
        return self.discovered_models

    def _discover_in_directory(self, directory: str) -> None:
        """
        Descobre modelos em um diretório específico.

        Args:
            directory: Caminho do diretório para buscar
        """
        for root, dirs, files in os.walk(directory):
            # Pular diretórios __pycache__
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            for file in files:
                if file.endswith(".py") and file != "__init__.py":
                    self._discover_in_file(root, file)

    def _discover_in_file(self, directory: str, filename: str) -> None:
        """
        Descobre modelos em um arquivo específico.

        Args:
            directory: Diretório do arquivo
            filename: Nome do arquivo
        """
        # Só processar arquivos que provavelmente contêm modelos
        if not self._should_process_file(filename):
            return

        try:
            # Construir o nome do módulo
            relative_path = os.path.relpath(directory, self.app_root)
            module_name = relative_path.replace(os.sep, ".")
            if module_name == ".":
                module_name = filename[:-3]  # Remove .py
            else:
                module_name = f"{module_name}.{filename[:-3]}"

            # Importar o módulo
            module = importlib.import_module(f"app.{module_name}")

            # Buscar classes que herdam de db.Model
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if self._is_model_class(obj):
                    self.discovered_models[name] = obj
                    print(f"  📦 Modelo descoberto: {name} em {module_name}")

        except Exception as e:
            # Silenciar erros de importação para não quebrar o sistema
            print(f"  ⚠️  Erro ao processar {filename}: {str(e)}")

    def _should_process_file(self, filename: str) -> bool:
        """
        Verifica se um arquivo deve ser processado para descoberta de modelos.

        Args:
            filename: Nome do arquivo

        Returns:
            True se o arquivo deve ser processado
        """
        # Só processar arquivos models.py ou que contenham 'model' no nome
        return (filename == "models.py" or "model" in filename.lower()) and filename != "__init__.py"

    def _is_model_class(self, obj: Type) -> bool:
        """
        Verifica se uma classe é um modelo SQLAlchemy.

        Args:
            obj: Classe para verificar

        Returns:
            True se for um modelo válido
        """
        try:
            # Verificar se é uma classe válida
            if not inspect.isclass(obj):
                return False

            # Verificar se herda de db.Model
            if not issubclass(obj, db.Model):
                return False

            # Verificar se não é uma classe abstrata
            if getattr(obj, "__abstract__", False):
                return False

            # Verificar se tem __tablename__ definido
            if not hasattr(obj, "__tablename__"):
                return False

            # Verificar se __tablename__ não é None
            if obj.__tablename__ is None:
                return False

            # Verificar se não é uma classe de enum
            if hasattr(obj, "__members__"):  # Enum classes
                return False

            return True

        except (TypeError, AttributeError, ValueError):
            return False

    def import_all_models(self) -> Dict[str, Type]:
        """
        Importa todos os modelos descobertos.

        Returns:
            Dicionário com modelos importados
        """
        # Descobrir modelos se ainda não foram descobertos
        if not self.discovered_models:
            self.discover_models()

        # Importar cada modelo para registrar no SQLAlchemy
        for model_name, model_class in self.discovered_models.items():
            try:
                # A importação já foi feita durante a descoberta
                # Aqui apenas verificamos se está registrado
                if hasattr(model_class, "__tablename__"):
                    print(f"  ✅ Modelo {model_name} registrado com sucesso")
            except Exception as e:
                print(f"  ❌ Erro ao registrar modelo {model_name}: {str(e)}")

        return self.discovered_models

    def get_model_by_name(self, model_name: str) -> Type:
        """
        Obtém um modelo pelo nome.

        Args:
            model_name: Nome do modelo

        Returns:
            Classe do modelo ou None se não encontrado
        """
        return self.discovered_models.get(model_name)

    def list_models(self) -> List[str]:
        """
        Lista todos os nomes dos modelos descobertos.

        Returns:
            Lista com nomes dos modelos
        """
        return list(self.discovered_models.keys())


# Instância global do descobridor de modelos
model_discovery = ModelDiscovery()


def auto_import_models() -> Dict[str, Type]:
    """
    Função de conveniência para importar todos os modelos automaticamente.

    Returns:
        Dicionário com modelos importados
    """
    return model_discovery.import_all_models()
