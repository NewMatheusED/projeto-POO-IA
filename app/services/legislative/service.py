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
        self.system_prompt = """Trata-se de um projeto analitico com base em dados. E necessario estruturar as informacoes em formato JSON. Toda a analise deve ser realizada utilizando as indicacoes oficiais do Brasil (leis, normas e dados oficiais).

Voce precisa enviar a resposta principal sendo um JSON com as chaves exatas abaixo:

* contexto_da_epoca

* resumo_objetivo

* interpretacao_simplificada

* avaliacao_parametrica (lista de objetos)

* tabela_markdown (string com a tabela solicitada em formato markdown)

* nota_media (numero)

Regras e formato de avaliacao_parametrica: deve ser uma lista de objetos JSON (cada objeto representa um criterio) com as chaves validas para banco de dados:

* criterio (string, nome do criterio)

* resumo_interpretacao (string, breve interpretacao do criterio)

* nota (inteiro 0 a 10)

* justificativa (string, explicando a nota relacionando ao metodo de avaliacao)

A nota_media deve receber apenas o resultado numerico da media aritmetica simples das notas que forem *maiores que 0* (descartar notas = 0). Se todas as notas forem 0, nota_media = 0. Use apenas numeros (sem texto) em nota e nota_media.

Ao citar fontes, priorize documentos oficiais brasileiros (leis, decretos, portarias, IBGE, Ministerio correspondente etc.). Se usar dados observados (item 7), referencie a fonte oficial e a data dos dados.

Sempre retorne nomes de chaves em snake_case, sem acentos, e formatos compativeis com banco de dados. O objeto JSON principal deve ser o unico output estruturado (ainda pode incluir a tabela_markdown para visualizacao)."""

        self.user_prompt_template = """Analise o seguinte Projeto de Lei/PEC: {{project_id}}

Quero que voce faca:

1. contexto_da_epoca: descreva o cenario politico, economico e social quando o projeto/PEC foi proposto (3–6 paragrafos curtos). Cite, quando possivel, datas e fontes oficiais brasileiras.

2. resumo_objetivo: explique em ate 10 linhas o que a proposta propoe. *Evite usar acentos ou espacos desnecessarios que gastem processamento* (use texto simples, sem caracteres especiais se possivel).

3. interpretacao_simplificada: explique em linguagem acessivel e direta o que muda na pratica para os cidadaos e para o pais (3–6 linhas).

4. avaliacao_parametrica: faca avaliacao (nota 0–10, restrita a numeros) nos criterios abaixo. Se um topico NAO se relaciona com a proposta, atribua 0 (nulo). Se fizer sentido, atribua nota entre 1 e 10. Para cada criterio, inclua criterio, resumo_interpretacao, nota e justificativa (a justificativa deve relacionar explicitamente os pontos considerados segundo o metodo de avaliacao indicado). Os criterios a avaliar sao:

   impacto_social: avaliar redistribuicao de recursos e acesso a direitos basicos; considerar grupos beneficiados ou prejudicados; verificar reducao ou ampliacao da desigualdade; analisar efeitos em bem-estar, qualidade de vida, mobilidade social e inclusao; avaliar impactos sobre pobreza, emprego, moradia e servicos essenciais; considerar grau de alcance da medida.

impacto_economico: julgar sustentabilidade fiscal e efeitos na economia; analisar receitas, despesas, endividamento e eficiencia do gasto; verificar impacto no PIB, investimentos, produtividade e inflacao; avaliar geracao de empregos; examinar estimulos a cadeias produtivas, competitividade, exportacoes e balanco comercial; identificar riscos de sobrecarga orcamentaria ou aumento de tributos.

impacto_politico_institucional: avaliar efeitos na governabilidade e autonomia institucional; considerar equilibrio entre poderes e entes federativos; analisar se cria dependencia politica ou reforca capacidade administrativa; observar transparencia, participacao social e viabilidade de implementacao; verificar conflitos entre orgaos e governos.

impacto_legal_constitucional: examinar compatibilidade juridica e riscos de judicializacao; verificar confronto com principios constitucionais e direitos fundamentais; identificar necessidade de alteracao constitucional ou regulamentacao; avaliar riscos de inconstitucionalidade; analisar clareza normativa e lacunas; estimar probabilidade de questionamento judicial.

impacto_ambiental: julgar efeitos sobre recursos naturais e sustentabilidade; avaliar uso e preservacao de agua, solo, fauna e flora; considerar emissoes de carbono, residuos e poluicao; verificar compatibilidade com metas ambientais; analisar impacto sobre biodiversidade e equilibrio ecologico; observar incentivos a praticas sustentaveis.

impacto_regional_setorial: analisar efeitos entre regioes e setores economicos; identificar impactos em segmentos estrategicos; avaliar alteracoes em cadeias produtivas locais; observar dependencia economica regional; julgar estimulacao ou retracao de polos industriais; verificar desigualdades territoriais.

impacto_tecnologico_inovacao: avaliar estimulo ou limitacao a inovacao e P&D; observar adocao tecnologica e infraestrutura digital; analisar politicas de transformacao digital; verificar impacto sobre startups, universidades e centros de pesquisa; considerar regulacao de novas tecnologias; avaliar competitividade e produtividade.

impacto_internacional_geopolitico: examinar alinhamento com acordos internacionais; verificar efeitos em comercio exterior, parcerias e imagem diplomatica; analisar cumprimento de tratados; avaliar alinhamento com politicas externas e compromissos ambientais.

educacao: analisar impacto no acesso, qualidade e financiamento da educacao; avaliar formacao e valorizacao de professores; considerar reducao de desigualdades; julgar fortalecimento de politicas publicas e programas de inclusao.

saude: avaliar impacto no SUS e sistema de saude; considerar acesso, financiamento e capacidade hospitalar; observar vacinacao e prevencao; analisar desigualdades regionais e fortalecimento da atencao basica.

seguranca: analisar impacto na seguranca publica; avaliar atuacao policial e politicas de prevencao; considerar protecao de direitos civis e sistema prisional; verificar combate ao crime e preservacao da ordem publica.

saneamento_basico: avaliar impacto no acesso a agua potavel, esgoto e coleta de residuos; considerar destinacao final e reciclabilidade; analisar investimentos em infraestrutura; observar efeitos em saude publica e qualidade de vida.

5. Para cada justificativa, explique claramente *por que* deu a nota, relacionando com os metodos descritos acima e citando, quando possivel, referencias oficiais brasileiras (incluir nomes de orgaos e, se possivel, datas).

6. Se a PEC/projeto ja tiver sido aprovado/integrado, inclua efeitos_observados (um campo opcional dentro do objeto do criterio ou um campo separado efeitos_observados) com dados observados ate a data mais recente disponivel e a fonte oficial (ex.: IBGE, Ministerio da Saude etc.). Se nao houver dados, indique explicitamente "sem dados observados".

7. formato_de_saida: alem do JSON, gere tabela_markdown com colunas: Criterio | Resumo/Interpretacao | Nota (0–10) | Justificativa (Metodo de Avaliacao) — cada linha corresponde a um item de avaliacao_parametrica. A tabela sera incluida como string no campo tabela_markdown.

8. nota_media: pegue a coluna nota (0–10), calcule a media aritmetica *desconsiderando as notas = 0*. Preencha nota_media com o numero (float) arredondado para duas casas decimais. Se todas as notas forem 0, nota_media = 0.

9. observacoes_metodologicas: inclua um pequeno objeto observacoes_metodologicas (chave em snake_case) que descreva os limites da analise, assumcoes feitas, e as fontes oficiais prioritarias usadas (ex.: lista curta: "Constituicao Federal, IBGE, Ministerio da Saude, Ministerio da Educacao, MMA, ANEEL..." etc.). Esse objeto deve conter chaves: limites, assuncoes e fontes_prioritarias (array).

10. Linguagem e formato: todo o conteudo deve estar em portugues (pt-BR). Use chaves sem acento e snake_case. Texto corrido pode ter acentos exceto onde solicitado (resumo_objetivo: evitar acentos/espacos extras). Nao inclua qualquer outro conteudo fora do JSON principal."""

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
        # Campos obrigatórios principais
        required_fields = [
            "contexto_da_epoca",
            "resumo_objetivo",
            "interpretacao_simplificada",
            "avaliacao_parametrica",
            "tabela_markdown",
            "nota_media"
        ]

        # Verifica campos obrigatórios
        for field in required_fields:
            if field not in data:
                return False

        # Valida nota_media (deve ser número)
        nota_media = data.get("nota_media")
        if not isinstance(nota_media, (int, float)) or nota_media < 0:
            return False

        # Verifica avaliações paramétricas
        avaliacoes = data.get("avaliacao_parametrica", [])
        if not isinstance(avaliacoes, list) or len(avaliacoes) == 0:
            return False

        # Verifica estrutura de cada avaliação
        for avaliacao in avaliacoes:
            required_av_fields = ["criterio", "resumo_interpretacao", "nota", "justificativa"]
            for field in required_av_fields:
                if field not in avaliacao:
                    return False

            # Valida nota
            nota = avaliacao.get("nota")
            if not isinstance(nota, int) or not (0 <= nota <= 10):
                return False

        # Valida observacoes_metodologicas se presente (deve ter estrutura correta)
        obs_metodologicas = data.get("observacoes_metodologicas")
        if obs_metodologicas is not None:
            if not isinstance(obs_metodologicas, dict):
                return False
            # Verifica chaves esperadas
            expected_keys = ["limites", "assuncoes", "fontes_prioritarias"]
            for key in expected_keys:
                if key not in obs_metodologicas:
                    return False
            # Verifica se fontes_prioritarias é uma lista
            if not isinstance(obs_metodologicas.get("fontes_prioritarias"), list):
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
