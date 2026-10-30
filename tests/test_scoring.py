"""Testes da pontuação — rodam sem internet:  python -m unittest discover -s tests"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agua import scoring  # noqa: E402


def avalia(titulo, resumo="", fonte="G1"):
    return scoring.avaliar(titulo, resumo, fonte)


class TestaAceita(unittest.TestCase):
    def test_santa_cruz_prioridade_maxima(self):
        r = avalia(
            "Interligação de rede pode afetar abastecimento de água em quatro bairros de Santa Cruz",
            "Serviço acontece nesta quinta-feira, das 8h às 18h.",
        )
        self.assertIsNotNone(r)
        self.assertTrue(r["priority"])
        self.assertIn("Santa Cruz", r["tags"])
        self.assertGreaterEqual(r["score"], 80)

    def test_guandu_prioridade(self):
        r = avalia(
            "Manutenção da Cedae no Guandu interromperá o abastecimento na capital",
            "Paralisação começa às 6h de terça-feira.",
        )
        self.assertIsNotNone(r)
        self.assertTrue(r["priority"])
        self.assertGreaterEqual(r["score"], 80)

    def test_zona_oeste_prioridade(self):
        r = avalia(
            "Parada do Guandu: Rio+Saneamento fará 20 obras e alerta para falta d'água na Zona Oeste",
        )
        self.assertIsNotNone(r)
        self.assertTrue(r["priority"])
        self.assertIn("Zona Oeste", r["tags"])

    def test_capital_sem_bairro_entra_mas_nao_alerta(self):
        r = avalia(
            "Cedae anuncia suspensão do abastecimento no Rio por 24 horas",
            "Medida afeta bairros de várias regiões.",
        )
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r["score"], 45)

    def test_bairro_especifico_com_agua(self):
        r = avalia(
            "Lapa, Catete, Glória, Flamengo, Urca e Leme",
            "Aviso de interrupção no abastecimento para manutenção da rede nesta quarta.",
            "Águas do Rio",
        )
        self.assertIsNotNone(r)
        self.assertIn("fonte oficial", r["tags"])


class TestaRejeita(unittest.TestCase):
    def test_outro_municipio(self):
        self.assertIsNone(avalia(
            "Chuvas interrompem abastecimento em Barra do Piraí",
            "Devido às chuvas registradas no estado do Rio de Janeiro.",
            "CEDAE",
        ))

    def test_outro_municipio_2(self):
        self.assertIsNone(avalia(
            "Cedae executa manutenção na Estação de Tratamento de Água em Italva",
            "Serviço no noroeste fluminense.",
            "CEDAE",
        ))

    def test_conta_de_agua(self):
        self.assertIsNone(avalia(
            "Conta da Cedae ganha novo modelo a partir de 6 de outubro",
            "Novo layout traz informações sobre consumo.",
        ))

    def test_saneamento_generico(self):
        self.assertIsNone(avalia(
            "Geração de renda: melhorias no saneamento estão abrindo espaço para novos negócios",
            "Projeto social na Zona Oeste.",
            "Águas do Rio",
        ))

    def test_sem_termo_de_agua(self):
        self.assertIsNone(avalia(
            "Prefeitura anuncia obras de drenagem na Zona Oeste",
            "Investimento de R$ 10 milhões.",
        ))

    def test_cidade_fora_do_rj(self):
        self.assertIsNone(avalia(
            "Falta de água atinge bairros de São Paulo após rompimento de adutora",
        ))


class TestaFaixas(unittest.TestCase):
    def test_score_no_intervalo(self):
        r = avalia("Falta de água em Santa Cruz após vazamento", "", "G1")
        self.assertIsNotNone(r)
        self.assertGreaterEqual(r["score"], 0)
        self.assertLessEqual(r["score"], 100)

    def test_normalizacao_perde_pontos(self):
        urgente = avalia("Vazamento interrompe abastecimento em Santa Cruz")
        normal = avalia("Abastecimento em Santa Cruz entra em normalização após vazamento")
        self.assertGreater(urgente["score"], normal["score"])

    def test_obra_nao_e_urgencia(self):
        r = avalia(
            "Cedae inicia obras da nova estação de água do Guandu; investimento é de R$ 2,1 bilhões"
        )
        self.assertIsNotNone(r)
        self.assertLess(r["score"], 60)


if __name__ == "__main__":
    unittest.main()
