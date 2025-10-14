import logging

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Instância global do SQLAlchemy para ser inicializada na application factory
db = SQLAlchemy()

logger = logging.getLogger(__name__)


# Importar todos os modelos automaticamente
def import_all_models():
    """
    Importa todos os modelos automaticamente.
    """
    try:
        import importlib
        import inspect
        import os

        # Caminho para serviços
        services_path = os.path.join(os.path.dirname(__file__), "services")

        if os.path.exists(services_path):
            for root, dirs, files in os.walk(services_path):
                # Pular __pycache__
                dirs[:] = [d for d in dirs if d != "__pycache__"]

                for file in files:
                    if file == "models.py":
                        # Construir nome do módulo
                        relative_path = os.path.relpath(root, os.path.dirname(__file__))
                        module_name = relative_path.replace(os.sep, ".")
                        module_name = f"app.{module_name}.models"

                        try:
                            # Importar o módulo
                            module = importlib.import_module(module_name)

                            # Buscar classes que herdam de db.Model
                            for name, obj in inspect.getmembers(module, inspect.isclass):
                                if inspect.isclass(obj) and hasattr(obj, "__bases__") and db.Model in obj.__bases__ and hasattr(obj, "__tablename__") and not getattr(obj, "__abstract__", False):
                                    print(f"  📦 Modelo descoberto automaticamente: {name}")
                        except Exception as e:
                            print(f"❌ Erro ao importar modelo {name}: {str(e)}")
                            pass

        print("✅ Todos os modelos foram importados com sucesso!")
        return True

    except Exception as e:
        print(f"❌ Erro ao importar modelos: {str(e)}")
        return False


def init_db(app):
    """Inicializa a extensão de banco com a aplicação."""
    db.init_app(app)

    # Testa a conexão com o banco de dados apenas se as variáveis estiverem definidas
    with app.app_context():
        try:
            # Importar todos os modelos automaticamente ANTES de criar as tabelas
            import_all_models()

            # Tentar conectar com retry logic
            max_retries = 5
            retry_delay = 5  # segundos
            
            for attempt in range(max_retries):
                try:
                    print(f"🔄 Tentativa {attempt + 1}/{max_retries} de conexão com o banco...")
                    test_database_connection()
                    print("✅ Conexão estabelecida com sucesso!")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"⚠️  Tentativa {attempt + 1} falhou: {str(e)}")
                        print(f"⏳ Aguardando {retry_delay}s antes de tentar novamente...")
                        import time
                        time.sleep(retry_delay)
                    else:
                        raise
            
            create_tables()

        except Exception as e:
            print(f"❌ Não foi possível conectar ao banco após {max_retries} tentativas: {str(e)}")
            print("⚠️  A aplicação continuará rodando, mas pode haver problemas de conexão")
            logger.error(f"❌ Erro ao inicializar banco de dados: {str(e)}")


def create_tables():
    """Cria todas as tabelas no banco de dados."""
    try:
        # Verifica se as tabelas já existem antes de tentar criar
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()

        if existing_tables:
            print(f"📋 Tabelas já existem no banco: {len(existing_tables)} tabelas")
            print("⏭️  Pulando criação de tabelas (já existem)")
            return True

        # Se não existem tabelas, cria todas
        print("🔧 Criando tabelas no banco de dados...")
        db.create_all()

        print("✅ Tabelas criadas com sucesso!")
        print(f"📋 Tabelas existentes no banco: {existing_tables}")

        return True
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {str(e)}")

        if "concurrent DDL" in str(e):
            print("⚠️  Erro de DDL concorrente detectado - tabelas podem estar sendo criadas por outro processo")
            print("⚠️  A aplicação continuará rodando")
            return True
        raise


def test_database_connection():
    """Testa a conexão com o banco de dados."""
    try:
        # Mostrar informações de conexão (sem senha)
        import os
        from urllib.parse import urlparse
        
        db_uri = os.getenv("SQLALCHEMY_DATABASE_URI") or "não configurado"
        parsed = urlparse(db_uri)
        
        print(f"🔍 Tentando conectar ao MySQL...")
        print(f"   Host: {parsed.hostname or 'não especificado'}")
        print(f"   Porta: {parsed.port or 'padrão (3306)'}")
        print(f"   Database: {parsed.path.lstrip('/') or 'não especificado'}")
        print(f"   User: {parsed.username or 'não especificado'}")
        
        # Executa uma query simples para testar a conexão
        db.session.execute(text("SELECT 1"))
        print("✅ Conexão com banco de dados estabelecida com sucesso!")
        logger.info("✅ Conexão com banco de dados estabelecida com sucesso!")
        return True
    except SQLAlchemyError as e:
        error_msg = str(e)
        # Se for erro de DDL concorrente, não falha a aplicação
        if "concurrent DDL" in error_msg:
            print("⚠️  Erro de DDL concorrente durante teste de conexão")
            print("⚠️  Isso é normal durante inicialização de múltiplos containers")
            print("⚠️  A aplicação continuará rodando")
            return True

        print(f"❌ Erro ao conectar com banco de dados: {error_msg}")
        print("Verifique se:")
        print("1. As variáveis de ambiente estão definidas corretamente")
        print("2. O servidor MySQL está rodando")
        print("3. As credenciais estão corretas")
        print("4. O banco de dados existe")
        print("5. O hostname está correto (deve ser 'mysql' no Docker)")
        logger.error(f"❌ Erro ao conectar com banco de dados: {error_msg}")
        logger.error("Verifique se:")
        logger.error("1. As variáveis de ambiente estão definidas corretamente")
        logger.error("2. O servidor MySQL está rodando")
        logger.error("3. As credenciais estão corretas")
        logger.error("4. O banco de dados existe")
        logger.error("5. O hostname está correto (deve ser 'mysql' no Docker)")
        raise
    except Exception as e:
        print(f"❌ Erro inesperado ao testar conexão: {str(e)}")
        logger.error(f"❌ Erro inesperado ao testar conexão: {str(e)}")
        raise
