"""
Serviço legislativo.

Fornece funcionalidades para análise de projetos de lei.
"""

from typing import Any, Dict

from app.services.legislative.models import AnaliseProjetoLei


class LegislativeService:
    """Serviço para operações legislativas."""

    def __init__(self):
        """Inicializa o serviço legislativo."""
        # Prompts fixos para análise legislativa
        self.system_prompt = """Trata-se de um projeto analítico com base em dados. É necessário estruturar as informações em uma tabela. Toda a análise deve ser realizada utilizando as indicações oficiais do Brasil. Voce precisa enviar a resposta principal sendo um JSON com as seguintes chaves:
contexto_epoca,
resumo_objetivo,
interpretacao_simplificada e
avaliacao_parametrica, que sera uma lista, contendo:

criterio | resumo | nota | justificativa. Sempre me retorne nomes de chaves validas para banco de dados."""

        self.user_prompt_template = """Analise o seguinte Projeto de Lei: {{project_id}}

Quero que você faça:

1. Contexto da Época: descreva o cenário político, econômico e social quando a PEC foi proposta.
2. Resumo Objetivo: explique em até 10 linhas o que a PEC propõe.
3. Interpretação Simplificada: explique em linguagem acessível o que muda na prática para os cidadãos e para o país.
4. Avaliação paramétrica (0 a 10) nos seguintes aspectos:
	Caso veja que os tópicos não se relacionam com o tema coloque 0 - ele significa nulo e 1 a nota mais baixa levando em conta que faca sentido. o resultado tem que ser restrito a numeros

   * Impacto Social
   * Impacto Econômico
   * Impacto Político-Institucional (estrutura de governo, autonomia de órgãos, governabilidade)
   * Impacto Legal/Constitucional (conformidade com direitos, riscos de questionamento judicial)
   * Impacto Ambiental (uso de recursos, sustentabilidade, políticas ambientais)
   * Impacto Regional/Setorial (diferenças regionais, efeitos em setores econômicos específicos)
   * Impacto Tecnológico/Inovação (incentivo ou restrição à tecnologia e pesquisa)
   * Impacto Internacional/Geopolítico (comércio exterior, acordos internacionais, imagem do país)
   * Impacto Temporal/Longo Prazo (sustentabilidade e necessidade de revisões futuras)

5. Para atribuir cada nota, use os seguintes métodos de avaliação:

   * Impacto Social: análise da redistribuição de recursos, grupos beneficiados ou prejudicados, efeitos sobre desigualdade, acesso a direitos básicos e bem-estar da população.
   * Impacto Econômico: sustentabilidade fiscal, déficit ou superávit projetado, impacto em crescimento econômico, investimentos e mercado de trabalho.
   * Impacto Político-Institucional: efeitos sobre a governabilidade, autonomia dos poderes, divisão de competências e capacidade de implementação.
   * Impacto Legal/Constitucional: compatibilidade com a Constituição, riscos de judicialização, necessidade de regulamentação adicional.
   * Impacto Ambiental: efeitos sobre recursos naturais, preservação ambiental, sustentabilidade de políticas públicas.
   * Impacto Regional/Setorial: efeitos desiguais entre regiões ou setores econômicos; impactos específicos em segmentos estratégicos.
   * Impacto Tecnológico/Inovação: estímulo ou limitação a inovação, digitalização, pesquisa e desenvolvimento.
   * Impacto Internacional/Geopolítico: alinhamento com acordos internacionais, repercussão em comércio exterior, imagem e relações diplomáticas.
   * Impacto Temporal/Longo Prazo: sustentabilidade das mudanças, previsibilidade de ajustes futuros, efeitos duradouros para políticas públicas.
6. Explique por que deu cada nota, relacionando com os critérios acima.
7. Caso a PEC já tenha sido aprovada, inclua efeitos observados até agora, se houver dados disponíveis.
8. Formato de saída: retorne em tabela, com colunas: Critério | Resumo/Interpretação | Nota (0–10) | Justificativa (Método de Avaliação).

preciso que os itens do 4 seja criado uma tabela e essa tabela seja o último tópico"""

    def get_system_prompt(self) -> str:
        """Retorna o prompt do sistema."""
        return self.system_prompt

    def get_user_prompt_template(self) -> str:
        """Retorna o template do prompt do usuário."""
        return self.user_prompt_template

    def build_user_prompt(self, project_id: str) -> str:
        """
        Constrói o prompt do usuário com o ID do projeto.

        Args:
            project_id: Código do projeto

        Returns:
            Prompt do usuário com variável substituída
        """
        return self.user_prompt_template.replace("{{project_id}}", project_id)

    def parse_ai_response(self, project_id: str, ai_response: Dict[str, Any]) -> AnaliseProjetoLei:
        """
        Parse da resposta da IA para estrutura padronizada.

        Args:
            project_id: Código do projeto
            ai_response: Resposta bruta da IA

        Returns:
            Análise estruturada do projeto
        """
        return AnaliseProjetoLei.from_ai_response(project_id, ai_response)

    def validate_analysis_data(self, data: Dict[str, Any]) -> bool:
        """
        Valida se os dados de análise estão completos.

        Args:
            data: Dados de análise para validar

        Returns:
            True se válido, False caso contrário
        """
        required_fields = ["avaliacao_parametrica"]

        # Verifica campos obrigatórios
        for field in required_fields:
            if field not in data:
                return False

        # Verifica avaliações paramétricas
        avaliacoes = data.get("avaliacao_parametrica", [])
        if not isinstance(avaliacoes, list) or len(avaliacoes) == 0:
            return False

        # Verifica estrutura de cada avaliação
        for avaliacao in avaliacoes:
            required_av_fields = ["criterio", "resumo", "nota", "justificativa"]
            for field in required_av_fields:
                if field not in avaliacao:
                    return False

            # Valida nota
            nota = avaliacao.get("nota")
            if not isinstance(nota, int) or not (0 <= nota <= 10):
                return False

        return True

    def calculate_statistics(self, analise: AnaliseProjetoLei) -> Dict[str, Any]:
        """
        Calcula estatísticas da análise.

        Args:
            analise: Análise do projeto

        Returns:
            Estatísticas calculadas
        """
        return analise.calcular_estatisticas()
