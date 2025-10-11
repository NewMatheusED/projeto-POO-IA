"""
Persistidor de dados.

Prepara estrutura para persistência, simulando operações de banco até estar pronto.
"""

import json
from typing import Any, Dict, List, Optional

from app.services.ia.data_processing.interfaces import DataPersistenceError, DataPersister


class MockPersister(DataPersister):
    """Persistidor mock para desenvolvimento enquanto o banco não está pronto."""

    def __init__(self, storage_file: Optional[str] = None):
        """
        Inicializa o persistidor mock.

        Args:
            storage_file: Arquivo para armazenar dados (opcional)
        """
        self.storage_file = storage_file or "mock_storage.json"
        self.data_store = self._load_storage()

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Salva dados no storage mock.

        Args:
            data: Dados para salvar

        Returns:
            Dados salvos com identificadores

        Raises:
            DataPersistenceError: Em caso de erro na persistência
        """
        try:
            # Gera ID único para o registro
            record_id = self._generate_record_id()

            # Prepara dados para salvar
            record_data = {"id": record_id, "created_at": self._get_current_timestamp(), "data": data, "status": "pending_validation"}

            # Salva no storage
            self.data_store[record_id] = record_data
            self._save_storage()

            # Retorna dados com identificadores
            saved_data = data.copy()
            saved_data["record_id"] = record_id
            saved_data["metadata"]["persistence_timestamp"] = record_data["created_at"]
            saved_data["metadata"]["storage_status"] = "saved_mock"

            return saved_data

        except Exception as e:
            raise DataPersistenceError(f"Erro ao salvar dados: {str(e)}")

    def get(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera dados pelo ID.

        Args:
            record_id: ID do registro

        Returns:
            Dados do registro ou None se não encontrado
        """
        return self.data_store.get(record_id)

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Lista todos os registros.

        Args:
            limit: Limite de registros para retornar

        Returns:
            Lista de registros
        """
        records = list(self.data_store.values())
        return records[:limit]

    def _generate_record_id(self) -> str:
        """Gera ID único para o registro."""
        import uuid

        return str(uuid.uuid4())

    def _load_storage(self) -> Dict[str, Any]:
        """Carrega dados do arquivo de storage."""
        try:
            with open(self.storage_file, encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_storage(self) -> None:
        """Salva dados no arquivo de storage."""
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(self.data_store, f, indent=2, ensure_ascii=False)

    def _get_current_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime

        return datetime.now().isoformat()


class DatabasePersister(DataPersister):
    """Persistidor para banco de dados (preparado para quando estiver pronto)."""

    def __init__(self, db_config: Dict[str, Any]):
        """
        Inicializa o persistidor de banco.

        Args:
            db_config: Configuração do banco de dados
        """
        self.db_config = db_config
        self.table_name = db_config.get("table_name", "processed_data")

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Salva dados no banco de dados.

        Args:
            data: Dados para salvar

        Returns:
            Dados salvos com identificadores

        Raises:
            DataPersistenceError: Em caso de erro na persistência
        """
        # TODO: Implementar quando o banco estiver pronto
        # Por enquanto, usa o persistidor mock
        mock_persister = MockPersister()
        return mock_persister.save(data)

    def _prepare_data_for_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara dados para inserção no banco.

        Args:
            data: Dados para preparar

        Returns:
            Dados formatados para o banco
        """
        # TODO: Implementar mapeamento para campos do banco
        return {
            "source": data.get("source"),
            "model": data.get("model"),
            "content": data.get("raw_content"),
            "extracted_data": json.dumps(data.get("extracted_data", {})),
            "enriched_data": json.dumps(data.get("enriched_data", {})),
            "metadata": json.dumps(data.get("metadata", {})),
            "created_at": self._get_current_timestamp(),
        }


class FilePersister(DataPersister):
    """Persistidor que salva dados em arquivos."""

    def __init__(self, base_path: str = "data/processed"):
        """
        Inicializa o persistidor de arquivos.

        Args:
            base_path: Caminho base para salvar arquivos
        """
        self.base_path = base_path
        import os

        os.makedirs(base_path, exist_ok=True)

    def save(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Salva dados em arquivo.

        Args:
            data: Dados para salvar

        Returns:
            Dados salvos com identificadores

        Raises:
            DataPersistenceError: Em caso de erro na persistência
        """
        try:
            import os
            import uuid

            # Gera nome do arquivo
            file_id = str(uuid.uuid4())
            filename = f"{file_id}.json"
            filepath = os.path.join(self.base_path, filename)

            # Prepara dados para salvar
            record_data = {"id": file_id, "created_at": self._get_current_timestamp(), "data": data}

            # Salva arquivo
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(record_data, f, indent=2, ensure_ascii=False)

            # Retorna dados com identificadores
            saved_data = data.copy()
            saved_data["record_id"] = file_id
            saved_data["metadata"]["persistence_timestamp"] = record_data["created_at"]
            saved_data["metadata"]["storage_status"] = "saved_file"
            saved_data["metadata"]["file_path"] = filepath

            return saved_data

        except Exception as e:
            raise DataPersistenceError(f"Erro ao salvar arquivo: {str(e)}")

    def _get_current_timestamp(self) -> str:
        """Retorna timestamp atual."""
        from datetime import datetime

        return datetime.now().isoformat()
