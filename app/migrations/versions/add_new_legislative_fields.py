"""Add new fields to legislative analysis tables

Revision ID: add_new_legislative_fields
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'add_new_legislative_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Adiciona novas colunas na tabela projetos_lei
    op.add_column('projetos_lei', sa.Column('contexto_da_epoca', sa.Text(), nullable=True))
    op.add_column('projetos_lei', sa.Column('resumo_objetivo', sa.Text(), nullable=True))
    op.add_column('projetos_lei', sa.Column('interpretacao_simplificada', sa.Text(), nullable=True))
    op.add_column('projetos_lei', sa.Column('tabela_markdown', sa.Text(), nullable=True))
    op.add_column('projetos_lei', sa.Column('observacoes_metodologicas', sa.JSON(), nullable=True))
    
    # Adiciona novas colunas na tabela avaliacoes_parametricas
    op.add_column('avaliacoes_parametricas', sa.Column('resumo_interpretacao', sa.Text(), nullable=True))
    op.add_column('avaliacoes_parametricas', sa.Column('justificativa', sa.Text(), nullable=True))
    op.add_column('avaliacoes_parametricas', sa.Column('efeitos_observados', sa.Text(), nullable=True))


def downgrade():
    # Remove colunas da tabela avaliacoes_parametricas
    op.drop_column('avaliacoes_parametricas', 'efeitos_observados')
    op.drop_column('avaliacoes_parametricas', 'justificativa')
    op.drop_column('avaliacoes_parametricas', 'resumo_interpretacao')
    
    # Remove colunas da tabela projetos_lei
    op.drop_column('projetos_lei', 'observacoes_metodologicas')
    op.drop_column('projetos_lei', 'tabela_markdown')
    op.drop_column('projetos_lei', 'interpretacao_simplificada')
    op.drop_column('projetos_lei', 'resumo_objetivo')
    op.drop_column('projetos_lei', 'contexto_da_epoca')

