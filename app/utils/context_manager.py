import logging
import threading
import time
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.database import db

_active_connections = 0
_max_connections = 60
_connection_counter_lock = threading.Lock()

logger = logging.getLogger(__name__)


# Guard utilitário: auto-rollback se a transação atual estiver inválida
def _is_failed_transaction(session):
    try:
        tx = session.get_transaction()
        return (tx is not None) and (not tx.is_active)
    except Exception:
        return False


def _install_auto_rollback_guard(session):
    """
    Envolve métodos críticos da sessão para garantir rollback automático
    caso a transação esteja inválida (failed transaction),
    evitando 'Can't reconnect until invalid transaction is rolled back'.
    """

    def wrap_method(name):
        original = getattr(session, name, None)
        if not callable(original):
            return

        def guarded(*args, **kwargs):
            if _is_failed_transaction(session):
                try:
                    session.rollback()
                except Exception:
                    # Se rollback falhar, re-levante original após tentar limpar
                    pass
            return original(*args, **kwargs)

        setattr(session, name, guarded)

    # Métodos comuns que disparam operações no DB. Evita envolver commit/flush para não gerar reentrância.
    for method_name in ("execute", "query", "scalars", "scalar", "get", "add", "add_all", "merge", "delete"):
        wrap_method(method_name)


@contextmanager
def get_db_session(max_retries=3, retry_delay=0.5, session_label=None, timeout=10):
    """
    Gerenciador de contexto avançado para sessões de banco de dados.

    Características:
    - Contagem de conexões ativas
    - Retry automático para erros de conexão
    - Logging detalhado
    - Medição de tempo de execução
    - Suporte a labels para identificar sessões em logs

    Args:
        max_retries (int): Número máximo de tentativas em caso de erro de conexão
        retry_delay (float): Tempo base de espera entre tentativas (em segundos)
        session_label (str): Identificador opcional para a sessão nos logs

    Yields:
        SQLAlchemy Session: Uma sessão de banco de dados ativa

    Raises:
        SQLAlchemyError: Erros relacionados ao banco de dados após tentativas de retry
        Exception: Outros erros não relacionados ao banco
    """
    global _active_connections

    start_wait = time.time()
    while True:
        with _connection_counter_lock:
            if _active_connections < _max_connections:
                _active_connections += 1
                current_connections = _active_connections
                break

        # Verifica timeout
        if time.time() - start_wait > timeout:
            raise Exception(f"Timeout esperando por conexão disponível. Conexões ativas: {_active_connections}")

        # Espera um pouco antes de tentar novamente
        time.sleep(0.1)

    session_id = id(threading.current_thread())
    session_info = f"[Sessão {session_id}]" + (f" [{session_label}]" if session_label else "")

    logger.debug(f"{session_info} Iniciando sessão. Conexões ativas: {current_connections}")
    start_time = time.time()

    # Estratégia de retry com backoff exponencial
    error_msg = ""  # Inicializar para uso no finally
    for attempt in range(max_retries):
        session = None
        try:
            session = db.session()
            # Evita expirar atributos no commit, permitindo uso dos objetos
            # fora do contexto da sessão sem gatilhar refresh automático
            # (que exigiria uma sessão ativa)
            try:
                session.expire_on_commit = False
            except Exception:
                # Em algumas implementações, a sessão pode não expor
                # diretamente o atributo; seguimos sem falhar.
                pass

            # Adicionar comentário SQL usando execução direta com text()
            if session_label:
                # Definir uma variável de sessão para identificar a origem
                session.execute(text(f"SET @session_label = '{session_label}'"))
                # Definir timeout para consultas (10 segundos)
                session.execute(text("SET SESSION MAX_EXECUTION_TIME=10000"))

            # Instala guard para auto-rollback em transação inválida
            _install_auto_rollback_guard(session)

            if attempt > 0:
                logger.info(f"{session_info} Tentativa {attempt + 1} / {max_retries} após falha de conexão")

            yield session

            # Se chegou aqui sem exceções, commit as alterações
            session.commit()

            # Registra o tempo de execução para análise de performance
            execution_time = time.time() - start_time
            if execution_time > 1.0:  # Log detalhado para consultas lentas
                logger.warning(f"{session_info} Sessão concluída em {execution_time:.2f}s (LENTA)")
            else:
                logger.debug(f"{session_info} Sessão concluída em {execution_time:.2f}s")

            # Limpar a mensagem de erro, pois não houve erro
            error_msg = ""

            # Sai do loop de retry se tudo ocorreu bem
            break

        except OperationalError as e:
            if session:
                session.rollback()
            error_msg = str(e)

            # Tratamento específico para "Too many connections"
            if "Too many connections" in error_msg:
                if attempt < max_retries - 1:
                    # Fechar a sessão atual antes de esperar
                    if session:
                        session.close()
                        session = None

                    backoff_time = retry_delay * (2**attempt)
                    logger.warning(f"{session_info} Erro 'Too many connections'. " f"Aguardando {backoff_time:.2f}s antes da próxima tentativa. " f"Conexões ativas: {current_connections}")
                    time.sleep(backoff_time)
                    continue

            # Tratamento para conexões perdidas
            elif "Lost connection" in error_msg or "server has gone away" in error_msg:
                if attempt < max_retries - 1:
                    backoff_time = retry_delay * (2**attempt)
                    logger.warning(f"{session_info} Erro de conexão perdida. Forçando novas conexões. " f"Aguardando {backoff_time:.2f}s antes da próxima tentativa.")
                    db.engine.dispose()  # Força o pool a criar novas conexões
                    time.sleep(backoff_time)
                    continue
                else:
                    logger.error(f"{session_info} Erro de conexão perdida persistente após {max_retries} tentativas.")

            # Outros erros operacionais
            logger.error(f"{session_info} Erro operacional do banco: {error_msg}")
            raise

        except SQLAlchemyError as e:
            # Erros de SQLAlchemy que não são de conexão
            if session:
                session.rollback()
            error_msg = str(e)
            logger.error(f"{session_info} Erro de SQLAlchemy: {error_msg}")
            raise

        except Exception as e:
            # Outros erros não relacionados ao banco
            if session:
                session.rollback()
            error_msg = str(e)
            logger.error(f"{session_info} Erro não esperado: {error_msg}")
            raise

        finally:
            # Sempre fecha a sessão, independente do resultado
            if session:
                session.close()

            # Decrementa o contador de conexões apenas se não vamos tentar novamente
            # ou se estamos no último retry
            if "Too many connections" not in error_msg or attempt == max_retries - 1:
                with _connection_counter_lock:
                    _active_connections -= 1
                    current_connections = _active_connections

            logger.debug(f"{session_info} Sessão encerrada. Conexões ativas restantes: {current_connections}")
