"""Pontuação de relevância: decide o que é notícia de abastecimento no Rio.

Regra de ouro: só entra o que fala de água/abastecimento E atinge a cidade do
Rio (capital), a Baixada ou o sistema Guandu. Notícia da CEDAE em Italva ou
Barra do Piraí fica de fora. Santa Cruz, Zona Oeste e Guandu pesam mais.
"""
from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------

_ACENTOS = {
    "á": "a", "à": "a", "â": "a", "ã": "a", "ä": "a",
    "é": "e", "è": "e", "ê": "e", "ë": "e",
    "í": "i", "ì": "i", "î": "i", "ï": "i",
    "ó": "o", "ò": "o", "ô": "o", "õ": "o", "ö": "o",
    "ú": "u", "ù": "u", "û": "u", "ü": "u",
    "ç": "c", "ñ": "n",
}

_APOSTROFOS = re.compile(r"['’`´]")


def norm(texto: str) -> str:
    if not texto:
        return ""
    t = texto.lower()
    t = _APOSTROFOS.sub(" ", t)
    t = "".join(_ACENTOS.get(c, c) for c in t)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9+]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _padded(texto: str) -> str:
    return " " + norm(texto) + " "


def _tem(texto_padded: str, termos) -> list[str]:
    return [t for t in termos if " " + t + " " in texto_padded]


# ---------------------------------------------------------------------------
# Vocabulário
# ---------------------------------------------------------------------------

# Prova de que a notícia é sobre abastecimento/operação de água.
AGUA = [
    "abastecimento", "desabastecimento", "falta de agua", "falta d agua",
    "sem agua", "interrupcao", "interrompe", "interrompera", "interrompido",
    "suspensao", "suspende", "suspenso", "racionamento", "adutora",
    "vazamento", "rompimento", "paralisacao", "paralisada", "paralisado",
    "manutencao", "reservatorio", "bombeamento", "recalque", "eta guandu",
    "sistema guandu", "tratamento de agua", "qualidade da agua",
    "rede de agua", "distribuicao de agua", "fornecimento de agua",
    "captacao", "estacao de tratamento", "guandu", "nivel do reservatorio",
]

# Gravidade / impacto imediato.
GRAVIDADE = [
    "interrompe", "interrompera", "interrompido", "interrupcao",
    "falta de agua", "falta d agua", "sem agua", "desabastecimento",
    "suspensao", "suspende", "racionamento", "rompimento", "vazamento",
    "paralisacao", "paralisada", "paralisado", "reduz producao",
    "reduzira", "afeta abastecimento", "afetara", "pode ficar sem agua",
]

# Recuperação: relevante, mas não é urgência.
RECUPERACAO = [
    "normalizacao", "normalizado", "retomada", "retoma", "volta a operar",
    "restabelecido", "concluida", "conclui",
]

# Capital e bairros do Rio.
CAPITAL = [
    "rio de janeiro", "capital fluminense", "municipio do rio",
    "cidade do rio", "no rio", "do rio", "na capital", "no municipio",
    "zona oeste", "zona norte", "zona sul", "centro do rio",
]

BAIRROS = [
    # Santa Cruz e entorno (peso máximo, mas listados aqui para o geo)
    "santa cruz", "guaratiba", "sepetiba", "cosmos", "paciencia",
    "ilha de guaraiba", "pedra de itauna", "pacotinga", "jesuítas",
    # Zona Oeste
    "campo grande", "bangu", "realengo", "senador camara", "padre miguel",
    "magalhaes bastos", "sulacap", "deodoro", "vila kennedy", "guadalupe",
    "itaguai", "seropedica",
    # Centro / Zona Sul / Zona Norte (notícias gerais da capital)
    "lapa", "catete", "gloria", "flamengo", "urca", "leme", "copacabana",
    "ipanema", "leblon", "botafogo", "tijuca", "meier", "madureira",
    "penha", "ilha do governador", "centro", "saude", "gamboa",
    "santo cristo", "sao cristovao", "caju", "mangueira", "vila isabel",
    "andarai", "maracana", "rio comprido", "osvaldo cruz", "braz de pina",
    "parada de lucas", "anchieta", "pavuna", "costa barros", "barros filho",
    "acari", "iraja", "vila da penha", "vicente de carvalho", "olaria",
    "ramos", "bonsucesso", "manguinhos", "benfica", "sao francisco xavier",
]

BAIXADA = [
    "baixada fluminense", "duque de caxias", "nova iguacu",
    "sao joao de meriti", "nilopolis", "mesquita", "queimados",
    "belford roxo", "japeri", "paracambi",
]

# Municípios atendidos pela CEDAE/Águas do Rio que NÃO são o foco. Se o texto
# citar um deles e não houver sinal de capital/Baixada/Guandu/Santa Cruz, fora.
OUTROS_MUNICIPIOS = [
    "barra do pirai", "engenheiro paulo de frontin", "italva", "sapucaia",
    "aperibe", "cambuci", "tres rios", "valenca", "vassouras",
    "miguel pereira", "paraiba do sul", "resende", "volta redonda",
    "barra mansa", "petropolis", "teresopolis", "nova friburgo",
    "bom jardim", "cantagalo", "cordeiro", "macuco", "sao sebastiao do alto",
    "itaocara", "santo antonio de padua", "mirai", "alem paraiba",
    "rio das flores", "pinheiral", "pirai", "rio claro", "mage",
    "guapimirim", "niteroi", "sao goncalo", "marica", "itaborai",
]

# Notícia de obra/investimento: relevante, mas não é urgência.
OBRA = ["investimento", "bilhoes", "nova estacao", "inaugura", "ampliacao", "entrega"]

SANTA_CRUZ = [
    "santa cruz", "guaratiba", "sepetiba", "cosmos", "paciencia",
    "ilha de guaraiba", "pedra de itauna", "pacotinga",
]

ZONA_OESTE = [
    "zona oeste", "campo grande", "bangu", "realengo", "senador camara",
    "padre miguel", "magalhaes bastos", "sulacap", "deodoro",
    "vila kennedy", "itaguai", "seropedica",
]

GUANDU = ["guandu", "eta guandu", "sistema guandu", "ribeira das neves"]

FONTES_OFICIAIS = ["aguas do rio", "cedae", "defesa civil", "rio+saneamento", "rio saneamento"]


def avaliar(titulo: str, resumo: str, fonte: str) -> dict | None:
    """Devolve {"score", "priority", "tags", "motivos"} ou None se irrelevante."""
    texto = f"{titulo} {resumo}"
    p = _padded(texto)

    if not _tem(p, AGUA):
        return None

    santa = _tem(p, SANTA_CRUZ)
    oeste = _tem(p, ZONA_OESTE)
    guandu = _tem(p, GUANDU)
    capital = _tem(p, CAPITAL)
    bairros = _tem(p, BAIRROS)
    baixada = _tem(p, BAIXADA)
    fora = _tem(p, OUTROS_MUNICIPIOS)

    # Nada de Rio/Baixada/Guandu no texto? Não é do nosso público.
    if not (santa or oeste or guandu or capital or bairros or baixada):
        return None
    # Notícia de outro município, sem relação com o sistema Guandu: fora.
    if fora and not (santa or oeste or guandu):
        return None

    gravidade = _tem(p, GRAVIDADE)
    recuperacao = _tem(p, RECUPERACAO)
    obra = _tem(p, OBRA)
    fonte_n = norm(fonte)
    oficial = any(f in fonte_n for f in FONTES_OFICIAIS)

    # Só o título decide a prioridade: resumo costuma citar "capital" de forma
    # genérica e isso não pode transformar notícia da Baixada em alerta.
    pt = _padded(titulo)
    capital_t = _tem(pt, CAPITAL)
    bairros_t = _tem(pt, BAIRROS)

    score = 35
    motivos: list[str] = []
    tags: list[str] = []

    if capital or bairros:
        score += 12
    if baixada:
        score += 8
        if not (capital or bairros):
            score -= 12  # Baixada sozinha é menos relevante que a capital
            tags.append("Baixada")
            motivos.append("afeta a Baixada")
    if gravidade:
        score += 20 + 5 * min(len(gravidade) - 1, 2)
        motivos.append("impacto imediato")
    if guandu:
        score += 22
        tags.append("Guandu")
        motivos.append("sistema Guandu")
    if santa:
        score += 38
        tags.append("Santa Cruz")
        motivos.append("atinge Santa Cruz/entorno")
    if oeste:
        score += 16
        tags.append("Zona Oeste")
        motivos.append("atinge a Zona Oeste")
    if oficial:
        score += 12
        tags.append("fonte oficial")
    if "manutencao" in " ".join(_tem(p, AGUA)):
        score += 6
    if recuperacao:
        score -= 12
        tags.append("normalização")
    if obra and not gravidade:
        score -= 12
        motivos.append("obra/investimento")

    score = max(0, min(100, score))

    priority = bool(santa or oeste or guandu)
    if oficial and gravidade and (capital_t or bairros_t):
        priority = True

    return {
        "score": score,
        "priority": priority,
        "tags": tags,
        "motivos": motivos,
    }
