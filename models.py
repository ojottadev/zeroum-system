"""
models.py - Modelos de banco de dados para o sistema de Assistência Técnica.
Utiliza Flask-SQLAlchemy com SQLite.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Cliente(db.Model):
    """
    Modelo de Cliente.
    Armazena dados de contato e identificação do cliente.
    """
    __tablename__ = 'clientes'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, index=True)
    cpf_cnpj = db.Column(db.String(25), nullable=True, index=True)
    telefone = db.Column(db.String(25), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=True)
    endereco = db.Column(db.String(255), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Relacionamentos com cascade restrito para proteger integridade referencial
    ordens_servico = db.relationship(
        'OrdemServico',
        backref='cliente',
        lazy=True,
        order_by='desc(OrdemServico.data_abertura)'
    )
    vendas = db.relationship(
        'Venda',
        backref='cliente',
        lazy=True,
        order_by='desc(Venda.data)'
    )

    def __repr__(self):
        return f'<Cliente #{self.id} {self.nome}>'


class OrdemServico(db.Model):
    """
    Modelo de Ordem de Serviço (O.S.).
    Controla o ciclo de vida da manutenção de equipamentos.
    """
    __tablename__ = 'ordens_servico'

    id = db.Column(db.Integer, primary_key=True)
    # Formato OS-YYYYMMDD-XXX
    numero = db.Column(db.String(30), unique=True, nullable=False, index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)

    # Informações do Equipamento
    tipo_equipamento = db.Column(db.String(60), nullable=True)  # Celular, Notebook, etc.
    marca = db.Column(db.String(60), nullable=True)
    modelo = db.Column(db.String(100), nullable=True)
    numero_serie = db.Column(db.String(100), nullable=True)
    senha_equipamento = db.Column(db.String(100), nullable=True)

    # Diagnóstico e Status
    problema = db.Column(db.Text, nullable=True)  # Reclamação do cliente
    diagnostico = db.Column(db.Text, nullable=True)  # Diagnóstico técnico
    # Status possíveis: Aberto, Em diagnóstico, Aguardando peça, Em reparo, Pronto, Entregue, Cancelado
    status = db.Column(db.String(40), default='Aberto', nullable=False, index=True)
    tecnico = db.Column(db.String(100), nullable=True)

    # Datas
    data_abertura = db.Column(db.DateTime, default=datetime.now, nullable=False)
    data_previsao = db.Column(db.Date, nullable=True)
    data_conclusao = db.Column(db.DateTime, nullable=True)
    data_entrega = db.Column(db.DateTime, nullable=True)

    # Valores financeiros da O.S.
    valor_mao_obra = db.Column(db.Float, default=0.0, nullable=False)
    valor_pecas = db.Column(db.Float, default=0.0, nullable=False)
    observacoes = db.Column(db.Text, nullable=True)

    # Relacionamento com Vendas vinculadas à O.S.
    vendas = db.relationship(
        'Venda',
        backref='ordem_servico',
        lazy=True,
        order_by='desc(Venda.data)'
    )

    @property
    def valor_total(self):
        """Retorna o valor total da O.S. somando mão de obra e peças."""
        return (self.valor_mao_obra or 0.0) + (self.valor_pecas or 0.0)

    def __repr__(self):
        return f'<OrdemServico {self.numero}>'


class Venda(db.Model):
    """
    Modelo de Venda.
    Pode ser avulsa ou associada a um cliente e/ou Ordem de Serviço.
    """
    __tablename__ = 'vendas'

    id = db.Column(db.Integer, primary_key=True)
    # Formato VD-YYYYMMDD-XXX
    numero = db.Column(db.String(30), unique=True, nullable=False, index=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=True)

    data = db.Column(db.DateTime, default=datetime.now, nullable=False)
    valor_total = db.Column(db.Float, default=0.0, nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=True)  # Dinheiro, PIX, Cartão, etc.
    # Status: Pendente, Pago, Cancelado
    status = db.Column(db.String(30), default='Pago', nullable=False, index=True)
    observacoes = db.Column(db.Text, nullable=True)

    # Itens vinculados à venda
    itens = db.relationship(
        'ItemVenda',
        backref='venda',
        cascade='all, delete-orphan',
        lazy=True
    )

    def __repr__(self):
        return f'<Venda {self.numero}>'


class ItemVenda(db.Model):
    """
    Modelo de Item de Venda.
    Representa uma peça ou serviço faturado na venda.
    """
    __tablename__ = 'itens_venda'

    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey('vendas.id'), nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    quantidade = db.Column(db.Float, default=1.0, nullable=False)
    valor_unitario = db.Column(db.Float, default=0.0, nullable=False)
    tipo = db.Column(db.String(20), default='peca', nullable=False)  # 'peca' ou 'servico'

    @property
    def subtotal(self):
        """Calcula o valor subtotal do item (quantidade * valor_unitario)."""
        return (self.quantidade or 0.0) * (self.valor_unitario or 0.0)

    def __repr__(self):
        return f'<ItemVenda {self.descricao}>'


class MovimentacaoCaixa(db.Model):
    """
    Modelo de Movimentação de Caixa (Entradas e Saídas).
    Registra fluxo financeiro, receitas de O.S./Vendas e despesas avulsas.
    """
    __tablename__ = 'movimentacoes_caixa'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10), nullable=False, index=True)  # 'entrada' ou 'saida'
    descricao = db.Column(db.String(255), nullable=False)
    valor = db.Column(db.Float, default=0.0, nullable=False)
    categoria = db.Column(db.String(60), default='Outros', nullable=False)
    forma_pagamento = db.Column(db.String(50), nullable=True)  # Dinheiro, PIX, Cartão de Crédito, etc.
    data = db.Column(db.DateTime, default=datetime.now, nullable=False, index=True)
    ordem_servico_id = db.Column(db.Integer, db.ForeignKey('ordens_servico.id'), nullable=True)
    venda_id = db.Column(db.Integer, db.ForeignKey('vendas.id'), nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.now, nullable=False)

    # Relacionamentos com O.S. e Venda
    ordem_servico = db.relationship('OrdemServico', backref=db.backref('movimentacoes_caixa', lazy=True, cascade='all'))
    venda = db.relationship('Venda', backref=db.backref('movimentacoes_caixa', lazy=True, cascade='all'))

    def __repr__(self):
        return f'<MovimentacaoCaixa #{self.id} {self.tipo}: R$ {self.valor:.2f}>'

