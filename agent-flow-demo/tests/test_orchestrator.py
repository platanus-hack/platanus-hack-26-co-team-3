"""Reparto de facturas entre sub-agentes: que la recursion siempre termine
y que ninguna factura se pierda ni se procese dos veces."""
import pytest

from agent_flow import orchestrator


def test_fallback_parte_en_dos_grupos():
    grupos = orchestrator._fallback_split(["A", "B", "C", "D"])
    assert len(grupos) == 2
    assert sorted(sum(grupos, [])) == ["A", "B", "C", "D"]


def test_fallback_con_dos_facturas_da_una_por_grupo():
    assert orchestrator._fallback_split(["A", "B"]) == [["A"], ["B"]]


def test_fallback_nunca_deja_un_grupo_igual_al_padre():
    """Si un hijo tuviera el mismo tamano que el padre, la recursion no
    avanza y el flujo no termina nunca."""
    for entrada in (["A", "B"], ["A", "B", "C"], list("ABCDEFG")):
        for grupo in orchestrator._fallback_split(entrada):
            assert 0 < len(grupo) < len(entrada)


def test_extract_text_con_string():
    assert orchestrator._extract_text("hola") == "hola"


def test_extract_text_con_bloques_de_anthropic():
    bloques = [{"type": "text", "text": "hola"}, {"type": "text", "text": "mundo"}]
    assert orchestrator._extract_text(bloques) == "hola mundo"


def test_extract_text_ignora_bloques_que_no_son_texto():
    bloques = [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "ok"}]
    assert orchestrator._extract_text(bloques) == "ok"


class _RespuestaFalsa:
    def __init__(self, content):
        self.content = content


class _LLMFalso:
    """Reemplaza la cadena prompt|llm: .invoke() devuelve lo que se le diga."""
    def __init__(self, texto):
        self.texto = texto

    def __or__(self, otro):
        return self

    def invoke(self, *args, **kwargs):
        return _RespuestaFalsa(self.texto)


@pytest.fixture
def plan_con(monkeypatch):
    def _armar(texto_del_llm):
        monkeypatch.setattr(orchestrator, "_make_llm", lambda *a, **k: _LLMFalso(texto_del_llm))
        monkeypatch.setattr(
            orchestrator.ChatPromptTemplate, "from_messages",
            classmethod(lambda cls, msgs: _LLMFalso(texto_del_llm)),
        )
        return orchestrator._delegate_plan(
            ["A", "B", "C"], "etiqueta", roxy=None,
            node_run_id="n1", parent_run_id=None,
        )
    return _armar


def test_acepta_un_reparto_valido(plan_con):
    assert plan_con('[["A","B"],["C"]]') == [["A", "B"], ["C"]]


def test_json_roto_cae_al_fallback(plan_con):
    grupos = plan_con("no soy json")
    assert sorted(sum(grupos, [])) == ["A", "B", "C"]


def test_factura_faltante_cae_al_fallback(plan_con):
    """El LLM se comio C: aceptarlo dejaria esa factura sin procesar."""
    grupos = plan_con('[["A"],["B"]]')
    assert sorted(sum(grupos, [])) == ["A", "B", "C"]


def test_factura_repetida_cae_al_fallback(plan_con):
    """B en dos grupos = dos sub-agentes escribiendo la misma factura."""
    grupos = plan_con('[["A","B"],["B","C"]]')
    assert sorted(sum(grupos, [])) == ["A", "B", "C"]


def test_un_solo_grupo_cae_al_fallback(plan_con):
    """Un unico grupo con todo no delega nada: la recursion no avanzaria."""
    grupos = plan_con('[["A","B","C"]]')
    assert len(grupos) == 2
    assert sorted(sum(grupos, [])) == ["A", "B", "C"]
