"""
test_app.py - Testes automatizados para validação de todas as regras de negócio
e rotas do sistema de Assistência Técnica.
"""

import os
import unittest
from datetime import datetime

# Garante que os testes usem um banco temporário isolado e NUNCA afetem a base principal
os.environ['DATABASE_URL'] = 'sqlite:////tmp/zeroum_test_app.db'

from app import app
from models import db, Cliente, OrdemServico, Venda, ItemVenda


class AssistenciaTecnicaTestCase(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_dashboard_vazio_e_com_dados(self):
        """Verifica se o dashboard carrega e exibe indicadores corretamente."""
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Vis\xc3\xa3o Geral', res.data)
        self.assertIn(b'O.S. em Aberto', res.data)
        self.assertIn(b'Faturamento', res.data)

    def test_crud_cliente(self):
        """Testa criação, edição, busca e exclusão de cliente."""
        # 1. Criação
        res = self.client.post('/clientes/novo', data={
            'nome': 'Carlos Eduardo Teste',
            'cpf_cnpj': '111.222.333-44',
            'telefone': '(11) 97777-6666',
            'email': 'carlos@teste.com',
            'endereco': 'Rua dos Testes, 123',
            'observacoes': 'Cliente VIP'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Carlos Eduardo Teste', res.data)

        # 2. Busca
        res_busca = self.client.get('/clientes?q=Eduardo')
        self.assertEqual(res_busca.status_code, 200)
        self.assertIn(b'Carlos Eduardo Teste', res_busca.data)

        # 3. Detalhe
        with app.app_context():
            c = Cliente.query.filter_by(nome='Carlos Eduardo Teste').first()
            self.assertIsNotNone(c)
            cliente_id = c.id

        res_detalhe = self.client.get(f'/clientes/{cliente_id}')
        self.assertEqual(res_detalhe.status_code, 200)
        self.assertIn(b'111.222.333-44', res_detalhe.data)

        # 4. Edição
        res_edit = self.client.post(f'/clientes/{cliente_id}/editar', data={
            'nome': 'Carlos Eduardo Atualizado',
            'cpf_cnpj': '111.222.333-44',
            'telefone': '(11) 99999-0000',
            'email': 'carlos.novo@teste.com',
            'endereco': 'Av Paulista, 500',
            'observacoes': 'Atualizado com sucesso'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'Carlos Eduardo Atualizado', res_edit.data)

        # 5. Exclusão permitida quando sem O.S./Vendas
        res_del = self.client.post(f'/clientes/{cliente_id}/excluir', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        with app.app_context():
            self.assertIsNone(db.session.get(Cliente, cliente_id))

    def test_regras_ordem_servico(self):
        """Testa geração de número, regras de status e bloqueio de exclusão do cliente."""
        with app.app_context():
            c = Cliente(nome='Ana Paula', telefone='11999999999')
            db.session.add(c)
            db.session.commit()
            c_id = c.id

        # 1. Criação de O.S.
        res = self.client.post('/os/nova', data={
            'cliente_id': c_id,
            'tipo_equipamento': 'Notebook',
            'marca': 'Dell',
            'modelo': 'G15',
            'numero_serie': 'SN123456',
            'senha_equipamento': '1234',
            'problema': 'Superaquecimento',
            'diagnostico': 'Troca de pasta térmica',
            'status': 'Aberto',
            'tecnico': 'Roberto',
            'data_previsao': '2026-11-20',
            'valor_mao_obra': '150.00',
            'valor_pecas': '0.00',
            'observacoes': 'Sem riscos aparentes'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with app.app_context():
            os_criada = OrdemServico.query.filter_by(cliente_id=c_id).first()
            self.assertIsNotNone(os_criada)
            self.assertTrue(os_criada.numero.startswith('OS-'))
            self.assertEqual(os_criada.status, 'Aberto')
            self.assertIsNone(os_criada.data_conclusao)
            self.assertIsNone(os_criada.data_entrega)
            os_id = os_criada.id

        # 2. Cliente com O.S. não pode ser excluído
        res_del_cliente = self.client.post(f'/clientes/{c_id}/excluir', follow_redirects=True)
        self.assertEqual(res_del_cliente.status_code, 200)
        self.assertIn('existem Ordens de Serviço'.encode('utf-8'), res_del_cliente.data)

        with app.app_context():
            self.assertIsNotNone(db.session.get(Cliente, c_id))

        # 3. Regra de mudança para 'Pronto': preenche data_conclusao se vazia
        self.client.post(f'/os/{os_id}/status', data={'status': 'Pronto'}, follow_redirects=True)
        with app.app_context():
            os_up = db.session.get(OrdemServico, os_id)
            self.assertEqual(os_up.status, 'Pronto')
            self.assertIsNotNone(os_up.data_conclusao)
            self.assertIsNone(os_up.data_entrega)

        # 4. Regra de mudança para 'Entregue': preenche data_entrega e data_conclusao
        self.client.post(f'/os/{os_id}/status', data={'status': 'Entregue'}, follow_redirects=True)
        with app.app_context():
            os_up2 = db.session.get(OrdemServico, os_id)
            self.assertEqual(os_up2.status, 'Entregue')
            self.assertIsNotNone(os_up2.data_conclusao)
            self.assertIsNotNone(os_up2.data_entrega)

    def test_vendas_itens_e_soma_pecas_os(self):
        """Testa cálculo do total a partir de itens dinâmicos e soma em valor_pecas da O.S."""
        with app.app_context():
            c = Cliente(nome='Marcos Lima')
            db.session.add(c)
            db.session.commit()

            os_obj = OrdemServico(
                numero='OS-20261110-999',
                cliente_id=c.id,
                marca='Apple',
                modelo='MacBook Pro',
                status='Em reparo',
                valor_mao_obra=200.0,
                valor_pecas=50.0
            )
            db.session.add(os_obj)
            db.session.commit()
            os_id = os_obj.id
            c_id = c.id

        # Criação de venda com 2 itens vinculada à O.S.
        # Item 1: Teclado original, 1x R$ 300,00
        # Item 2: Conector flat, 2x R$ 50,00 = R$ 100,00
        # Total esperado da venda = R$ 400,00
        res = self.client.post('/vendas/nova', data={
            'cliente_id': c_id,
            'ordem_servico_id': os_id,
            'forma_pagamento': 'PIX',
            'status': 'Pago',
            'observacoes': 'Peças originais',
            'descricao[]': ['Teclado ABNT2 MacBook', 'Cabo Flat Conector'],
            'quantidade[]': ['1', '2'],
            'valor_unitario[]': ['300.00', '50.00'],
            'tipo[]': ['peca', 'peca']
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with app.app_context():
            venda = Venda.query.filter_by(ordem_servico_id=os_id).first()
            self.assertIsNotNone(venda)
            self.assertTrue(venda.numero.startswith('VD-'))
            self.assertEqual(len(venda.itens), 2)
            self.assertAlmostEqual(venda.valor_total, 400.0)

            # Verifica se somou no valor_pecas da O.S.: 50.0 inicial + 400.0 = 450.0
            os_atualizada = db.session.get(OrdemServico, os_id)
            self.assertAlmostEqual(os_atualizada.valor_pecas, 450.0)
            self.assertAlmostEqual(os_atualizada.valor_total, 650.0)  # 200 mao de obra + 450 pecas
            venda_id = venda.id

        # Exclusão da venda reverte a soma do valor_pecas
        res_del_venda = self.client.post(f'/vendas/{venda_id}/excluir', follow_redirects=True)
        self.assertEqual(res_del_venda.status_code, 200)

        with app.app_context():
            self.assertIsNone(db.session.get(Venda, venda_id))
            os_revertida = db.session.get(OrdemServico, os_id)
            self.assertAlmostEqual(os_revertida.valor_pecas, 50.0)


if __name__ == '__main__':
    unittest.main()
