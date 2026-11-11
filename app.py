"""
app.py - Aplicação Web Flask para Assistência Técnica.
Gerencia Clientes, Ordens de Serviço (O.S.), Vendas e Dashboard com interface responsiva mobile-first.
"""

import os
from datetime import datetime, date
from calendar import monthrange
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, get_flashed_messages
)
from models import db, Cliente, OrdemServico, Venda, ItemVenda

# Configuração da Aplicação Flask
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'chave-secreta-assistencia-tecnica-2026')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    f"sqlite:///{os.path.join(basedir, 'assistencia_tecnica.db')}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa banco de dados com a aplicação
db.init_app(app)


# ==============================================================================
# FILTROS JINJA2 PERSONALIZADOS
# ==============================================================================

@app.template_filter('currency')
def format_currency(value):
    """Formata valor float/int no padrão monetário brasileiro (R$ 1.250,00)."""
    if value is None:
        value = 0.0
    try:
        val = float(value)
        formatted = f"{val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return "R$ 0,00"


@app.template_filter('format_date')
def format_date(value):
    """Formata datas no padrão brasileiro DD/MM/AAAA."""
    if not value:
        return "—"
    if isinstance(value, (datetime, date)):
        return value.strftime('%d/%m/%Y')
    return str(value)


@app.template_filter('format_datetime')
def format_datetime(value):
    """Formata data e hora no padrão brasileiro DD/MM/AAAA às HH:MM."""
    if not value:
        return "—"
    if isinstance(value, datetime):
        return value.strftime('%d/%m/%Y às %H:%M')
    elif isinstance(value, date):
        return value.strftime('%d/%m/%Y')
    return str(value)


@app.template_filter('status_os_badge')
def status_os_badge(status):
    """Retorna classes CSS Tailwind para crachás de status de O.S."""
    cores = {
        'Aberto': 'bg-sky-100 text-sky-800 border-sky-300 ring-sky-500/30',
        'Em diagnóstico': 'bg-purple-100 text-purple-800 border-purple-300 ring-purple-500/30',
        'Aguardando peça': 'bg-amber-100 text-amber-800 border-amber-300 ring-amber-500/30',
        'Em reparo': 'bg-blue-100 text-blue-800 border-blue-300 ring-blue-500/30',
        'Pronto': 'bg-emerald-100 text-emerald-800 border-emerald-300 ring-emerald-500/30',
        'Entregue': 'bg-slate-100 text-slate-800 border-slate-300 ring-slate-500/30',
        'Cancelado': 'bg-rose-100 text-rose-800 border-rose-300 ring-rose-500/30',
    }
    return cores.get(status, 'bg-gray-100 text-gray-800 border-gray-300 ring-gray-500/30')


@app.template_filter('status_venda_badge')
def status_venda_badge(status):
    """Retorna classes CSS Tailwind para crachás de status de Vendas."""
    cores = {
        'Pago': 'bg-emerald-100 text-emerald-800 border-emerald-300 ring-emerald-500/30',
        'Pendente': 'bg-amber-100 text-amber-800 border-amber-300 ring-amber-500/30',
        'Cancelado': 'bg-rose-100 text-rose-800 border-rose-300 ring-rose-500/30',
    }
    return cores.get(status, 'bg-gray-100 text-gray-800 border-gray-300 ring-gray-500/30')


# ==============================================================================
# FUNÇÕES UTILITÁRIAS / REGRAS DE NEGÓCIO
# ==============================================================================

def gerar_numero_os():
    """Gera um número sequencial único para a O.S. no formato OS-YYYYMMDD-XXX."""
    hoje_str = datetime.now().strftime('%Y%m%d')
    prefixo = f"OS-{hoje_str}-"
    ultima_os = OrdemServico.query.filter(
        OrdemServico.numero.like(f"{prefixo}%")
    ).order_by(OrdemServico.id.desc()).first()

    if ultima_os and ultima_os.numero:
        try:
            ultimo_seq = int(ultima_os.numero.split('-')[-1])
            novo_seq = ultimo_seq + 1
        except (ValueError, IndexError):
            novo_seq = 1
    else:
        novo_seq = 1

    return f"{prefixo}{novo_seq:03d}"


def gerar_numero_venda():
    """Gera um número sequencial único para a Venda no formato VD-YYYYMMDD-XXX."""
    hoje_str = datetime.now().strftime('%Y%m%d')
    prefixo = f"VD-{hoje_str}-"
    ultima_venda = Venda.query.filter(
        Venda.numero.like(f"{prefixo}%")
    ).order_by(Venda.id.desc()).first()

    if ultima_venda and ultima_venda.numero:
        try:
            ultimo_seq = int(ultima_venda.numero.split('-')[-1])
            novo_seq = ultimo_seq + 1
        except (ValueError, IndexError):
            novo_seq = 1
    else:
        novo_seq = 1

    return f"{prefixo}{novo_seq:03d}"


def aplicar_regras_status_os(os_obj, novo_status):
    """
    Aplica as regras de negócio para alteração de status da O.S.:
    - Ao mudar para 'Pronto', preenche data_conclusao se vazia.
    - Ao mudar para 'Entregue', preenche data_entrega e data_conclusao se vazias.
    """
    agora = datetime.now()
    os_obj.status = novo_status

    if novo_status == 'Pronto':
        if not os_obj.data_conclusao:
            os_obj.data_conclusao = agora

    elif novo_status == 'Entregue':
        if not os_obj.data_conclusao:
            os_obj.data_conclusao = agora
        if not os_obj.data_entrega:
            os_obj.data_entrega = agora


STATUS_OS_LISTA = [
    'Aberto',
    'Em diagnóstico',
    'Aguardando peça',
    'Em reparo',
    'Pronto',
    'Entregue',
    'Cancelado'
]

FORMAS_PAGAMENTO_LISTA = [
    'Dinheiro',
    'PIX',
    'Cartão de Débito',
    'Cartão de Crédito',
    'Boleto Bancário',
    'Transferência Bancária',
    'Outro'
]


# ==============================================================================
# ROTAS: 1. DASHBOARD
# ==============================================================================

@app.route('/')
def dashboard():
    """
    Dashboard principal do sistema.
    Exibe indicadores de O.S., faturamento mensal, clientes recentes e atalhos rápidos.
    """
    agora = datetime.now()
    inicio_mes = datetime(agora.year, agora.month, 1, 0, 0, 0)
    _, ultimo_dia = monthrange(agora.year, agora.month)
    fim_mes = datetime(agora.year, agora.month, ultimo_dia, 23, 59, 59)

    # 1. Quantidade de O.S. abertas (status: Aberto, Em diagnóstico, Aguardando peça, Em reparo)
    status_abertas = ['Aberto', 'Em diagnóstico', 'Aguardando peça', 'Em reparo']
    qtd_os_abertas = OrdemServico.query.filter(OrdemServico.status.in_(status_abertas)).count()

    # 2. Quantidade de O.S. prontas
    qtd_os_prontas = OrdemServico.query.filter_by(status='Pronto').count()

    # 3. Faturamento do mês atual (vendas com status "Pago")
    vendas_mes_pago = Venda.query.filter(
        Venda.status == 'Pago',
        Venda.data >= inicio_mes,
        Venda.data <= fim_mes
    ).all()
    faturamento_mes = sum(v.valor_total for v in vendas_mes_pago)

    # 4. Clientes novos no mês
    qtd_clientes_novos = Cliente.query.filter(
        Cliente.criado_em >= inicio_mes,
        Cliente.criado_em <= fim_mes
    ).count()

    # 5. Lista das 8 O.S. mais recentes
    os_recentes = OrdemServico.query.order_by(OrdemServico.data_abertura.desc()).limit(8).all()

    # 6. Lista das 5 vendas mais recentes
    vendas_recentes = Venda.query.order_by(Venda.data.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        qtd_os_abertas=qtd_os_abertas,
        qtd_os_prontas=qtd_os_prontas,
        faturamento_mes=faturamento_mes,
        qtd_clientes_novos=qtd_clientes_novos,
        os_recentes=os_recentes,
        vendas_recentes=vendas_recentes,
        mes_atual_nome=agora.strftime('%B de %Y')
    )


# ==============================================================================
# ROTAS: 2. CLIENTES
# ==============================================================================

@app.route('/clientes')
def clientes_lista():
    """Listagem de clientes com filtro de busca por nome, CPF/CNPJ ou telefone."""
    q = request.args.get('q', '').strip()
    query = Cliente.query

    if q:
        termo = f"%{q}%"
        query = query.filter(
            (Cliente.nome.ilike(termo)) |
            (Cliente.cpf_cnpj.ilike(termo)) |
            (Cliente.telefone.ilike(termo))
        )

    clientes = query.order_by(Cliente.nome.asc()).all()
    return render_template('clientes/lista.html', clientes=clientes, termo_busca=q)


@app.route('/clientes/novo', methods=['GET', 'POST'])
def clientes_novo():
    """Cadastro de novo cliente."""
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        cpf_cnpj = request.form.get('cpf_cnpj', '').strip()
        telefone = request.form.get('telefone', '').strip()
        email = request.form.get('email', '').strip()
        endereco = request.form.get('endereco', '').strip()
        observacoes = request.form.get('observacoes', '').strip()

        if not nome:
            flash('O campo Nome é obrigatório!', 'error')
            return render_template('clientes/form.html', cliente=None, acao='novo')

        novo_cliente = Cliente(
            nome=nome,
            cpf_cnpj=cpf_cnpj,
            telefone=telefone,
            email=email,
            endereco=endereco,
            observacoes=observacoes,
            criado_em=datetime.now()
        )
        db.session.add(novo_cliente)
        db.session.commit()

        flash(f'Cliente "{novo_cliente.nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes_detalhe', id=novo_cliente.id))

    return render_template('clientes/form.html', cliente=None, acao='novo')


@app.route('/clientes/<int:id>')
def clientes_detalhe(id):
    """Exibe o perfil e histórico completo de O.S. e Vendas de um cliente."""
    cliente = db.get_or_404(Cliente, id)
    return render_template('clientes/detalhe.html', cliente=cliente)


@app.route('/clientes/<int:id>/editar', methods=['GET', 'POST'])
def clientes_editar(id):
    """Edição dos dados de um cliente."""
    cliente = db.get_or_404(Cliente, id)

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('O campo Nome é obrigatório!', 'error')
            return render_template('clientes/form.html', cliente=cliente, acao='editar')

        cliente.nome = nome
        cliente.cpf_cnpj = request.form.get('cpf_cnpj', '').strip()
        cliente.telefone = request.form.get('telefone', '').strip()
        cliente.email = request.form.get('email', '').strip()
        cliente.endereco = request.form.get('endereco', '').strip()
        cliente.observacoes = request.form.get('observacoes', '').strip()

        db.session.commit()
        flash(f'Dados do cliente "{cliente.nome}" atualizados com sucesso!', 'success')
        return redirect(url_for('clientes_detalhe', id=cliente.id))

    return render_template('clientes/form.html', cliente=cliente, acao='editar')


@app.route('/clientes/<int:id>/excluir', methods=['POST'])
def clientes_excluir(id):
    """Exclusão de cliente. Bloqueia caso existam O.S. ou Vendas vinculadas."""
    cliente = db.get_or_404(Cliente, id)

    if cliente.ordens_servico or cliente.vendas:
        flash(
            'Não é possível excluir este cliente porque existem Ordens de Serviço ou Vendas vinculadas a ele.',
            'error'
        )
        return redirect(url_for('clientes_detalhe', id=cliente.id))

    nome = cliente.nome
    db.session.delete(cliente)
    db.session.commit()
    flash(f'Cliente "{nome}" foi excluído com sucesso.', 'success')
    return redirect(url_for('clientes_lista'))


# ==============================================================================
# ROTAS: 3. ORDENS DE SERVIÇO (O.S.)
# ==============================================================================

@app.route('/os')
def os_lista():
    """Listagem de Ordens de Serviço com filtro por status e busca geral."""
    status_filtro = request.args.get('status', '').strip()
    q = request.args.get('q', '').strip()

    query = OrdemServico.query.join(Cliente)

    if status_filtro:
        query = query.filter(OrdemServico.status == status_filtro)

    if q:
        termo = f"%{q}%"
        query = query.filter(
            (OrdemServico.numero.ilike(termo)) |
            (Cliente.nome.ilike(termo)) |
            (OrdemServico.marca.ilike(termo)) |
            (OrdemServico.modelo.ilike(termo))
        )

    ordens = query.order_by(OrdemServico.data_abertura.desc()).all()
    return render_template(
        'os/lista.html',
        ordens=ordens,
        status_lista=STATUS_OS_LISTA,
        status_selecionado=status_filtro,
        termo_busca=q
    )


@app.route('/os/nova', methods=['GET', 'POST'])
def os_nova():
    """Cadastro de nova Ordem de Serviço."""
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()

    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id')
        if not cliente_id:
            flash('Selecione um cliente para abrir a O.S.!', 'error')
            return render_template('os/form.html', os_obj=None, clientes=clientes, acao='nova', status_lista=STATUS_OS_LISTA)

        numero = gerar_numero_os()
        tipo_equipamento = request.form.get('tipo_equipamento', '').strip()
        marca = request.form.get('marca', '').strip()
        modelo = request.form.get('modelo', '').strip()
        numero_serie = request.form.get('numero_serie', '').strip()
        senha_equipamento = request.form.get('senha_equipamento', '').strip()
        problema = request.form.get('problema', '').strip()
        diagnostico = request.form.get('diagnostico', '').strip()
        status = request.form.get('status', 'Aberto')
        tecnico = request.form.get('tecnico', '').strip()
        observacoes = request.form.get('observacoes', '').strip()

        # Data de previsão
        data_previsao_str = request.form.get('data_previsao', '').strip()
        data_previsao = None
        if data_previsao_str:
            try:
                data_previsao = datetime.strptime(data_previsao_str, '%Y-%m-%d').date()
            except ValueError:
                data_previsao = None

        # Valores
        try:
            valor_mao_obra = float(request.form.get('valor_mao_obra', '0').replace(',', '.'))
        except (ValueError, TypeError):
            valor_mao_obra = 0.0

        try:
            valor_pecas = float(request.form.get('valor_pecas', '0').replace(',', '.'))
        except (ValueError, TypeError):
            valor_pecas = 0.0

        nova_os = OrdemServico(
            numero=numero,
            cliente_id=int(cliente_id),
            tipo_equipamento=tipo_equipamento,
            marca=marca,
            modelo=modelo,
            numero_serie=numero_serie,
            senha_equipamento=senha_equipamento,
            problema=problema,
            diagnostico=diagnostico,
            status=status,
            tecnico=tecnico,
            data_abertura=datetime.now(),
            data_previsao=data_previsao,
            valor_mao_obra=valor_mao_obra,
            valor_pecas=valor_pecas,
            observacoes=observacoes
        )

        # Regras de negócio de status
        aplicar_regras_status_os(nova_os, status)

        db.session.add(nova_os)
        db.session.commit()

        flash(f'Ordem de Serviço {nova_os.numero} gerada com sucesso!', 'success')
        return redirect(url_for('os_detalhe', id=nova_os.id))

    # Permite passar cliente_id pela URL (?cliente_id=X)
    cliente_preselecionado = request.args.get('cliente_id', type=int)
    return render_template(
        'os/form.html',
        os_obj=None,
        clientes=clientes,
        cliente_preselecionado=cliente_preselecionado,
        acao='nova',
        status_lista=STATUS_OS_LISTA
    )


@app.route('/os/<int:id>')
def os_detalhe(id):
    """Visualização detalhada da Ordem de Serviço."""
    os_obj = db.get_or_404(OrdemServico, id)
    return render_template(
        'os/detalhe.html',
        os_obj=os_obj,
        status_lista=STATUS_OS_LISTA
    )


@app.route('/os/<int:id>/editar', methods=['GET', 'POST'])
def os_editar(id):
    """Edição completa dos dados da O.S."""
    os_obj = db.get_or_404(OrdemServico, id)
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()

    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id')
        if not cliente_id:
            flash('O cliente é obrigatório!', 'error')
            return render_template('os/form.html', os_obj=os_obj, clientes=clientes, acao='editar', status_lista=STATUS_OS_LISTA)

        os_obj.cliente_id = int(cliente_id)
        os_obj.tipo_equipamento = request.form.get('tipo_equipamento', '').strip()
        os_obj.marca = request.form.get('marca', '').strip()
        os_obj.modelo = request.form.get('modelo', '').strip()
        os_obj.numero_serie = request.form.get('numero_serie', '').strip()
        os_obj.senha_equipamento = request.form.get('senha_equipamento', '').strip()
        os_obj.problema = request.form.get('problema', '').strip()
        os_obj.diagnostico = request.form.get('diagnostico', '').strip()
        os_obj.tecnico = request.form.get('tecnico', '').strip()
        os_obj.observacoes = request.form.get('observacoes', '').strip()

        # Previsão
        data_previsao_str = request.form.get('data_previsao', '').strip()
        if data_previsao_str:
            try:
                os_obj.data_previsao = datetime.strptime(data_previsao_str, '%Y-%m-%d').date()
            except ValueError:
                os_obj.data_previsao = None
        else:
            os_obj.data_previsao = None

        # Valores
        try:
            os_obj.valor_mao_obra = float(request.form.get('valor_mao_obra', '0').replace(',', '.'))
        except (ValueError, TypeError):
            os_obj.valor_mao_obra = 0.0

        try:
            os_obj.valor_pecas = float(request.form.get('valor_pecas', '0').replace(',', '.'))
        except (ValueError, TypeError):
            os_obj.valor_pecas = 0.0

        # Aplica mudança de status e regras automáticas
        novo_status = request.form.get('status', os_obj.status)
        aplicar_regras_status_os(os_obj, novo_status)

        db.session.commit()
        flash(f'Ordem de Serviço {os_obj.numero} atualizada com sucesso!', 'success')
        return redirect(url_for('os_detalhe', id=os_obj.id))

    return render_template(
        'os/form.html',
        os_obj=os_obj,
        clientes=clientes,
        acao='editar',
        status_lista=STATUS_OS_LISTA
    )


@app.route('/os/<int:id>/status', methods=['POST'])
def os_status_rapido(id):
    """Atualização rápida do status da O.S. (direto do card ou detalhe)."""
    os_obj = db.get_or_404(OrdemServico, id)
    novo_status = request.form.get('status', '').strip()

    if novo_status in STATUS_OS_LISTA:
        aplicar_regras_status_os(os_obj, novo_status)
        db.session.commit()
        flash(f'Status da O.S. {os_obj.numero} alterado para "{novo_status}".', 'success')
    else:
        flash('Status inválido informado.', 'error')

    # Redireciona de volta para a página que enviou ou para o detalhe
    next_url = request.form.get('next') or request.referrer or url_for('os_detalhe', id=os_obj.id)
    return redirect(next_url)


# ==============================================================================
# ROTAS: 4. VENDAS
# ==============================================================================

@app.route('/vendas')
def vendas_lista():
    """Listagem de Vendas com campo de busca por número ou nome do cliente."""
    q = request.args.get('q', '').strip()
    status_filtro = request.args.get('status', '').strip()

    query = Venda.query.outerjoin(Cliente)

    if status_filtro:
        query = query.filter(Venda.status == status_filtro)

    if q:
        termo = f"%{q}%"
        query = query.filter(
            (Venda.numero.ilike(termo)) |
            (Cliente.nome.ilike(termo))
        )

    vendas = query.order_by(Venda.data.desc()).all()
    return render_template('vendas/lista.html', vendas=vendas, termo_busca=q, status_filtro=status_filtro)


@app.route('/vendas/nova', methods=['GET', 'POST'])
def vendas_nova():
    """
    Criação de nova venda com múltiplos itens dinâmicos.
    Calcula valor_total automaticamente a partir dos itens.
    Se vinculada a uma O.S., soma o valor total no campo valor_pecas da O.S.
    """
    clientes = Cliente.query.order_by(Cliente.nome.asc()).all()
    ordens = OrdemServico.query.order_by(OrdemServico.data_abertura.desc()).all()

    if request.method == 'POST':
        cliente_id = request.form.get('cliente_id') or None
        ordem_servico_id = request.form.get('ordem_servico_id') or None
        forma_pagamento = request.form.get('forma_pagamento', 'PIX')
        status = request.form.get('status', 'Pago')
        observacoes = request.form.get('observacoes', '').strip()

        # Converte IDs
        cliente_id_val = int(cliente_id) if cliente_id else None
        os_id_val = int(ordem_servico_id) if ordem_servico_id else None

        # Se houver O.S. vinculada e cliente não informado, herda o cliente da O.S.
        if os_id_val and not cliente_id_val:
            os_vinculada = db.session.get(OrdemServico, os_id_val)
            if os_vinculada:
                cliente_id_val = os_vinculada.cliente_id

        # Captura itens dinâmicos
        descricoes = request.form.getlist('descricao[]')
        quantidades = request.form.getlist('quantidade[]')
        valores_unitarios = request.form.getlist('valor_unitario[]')
        tipos = request.form.getlist('tipo[]')

        itens_a_criar = []
        valor_total_calculado = 0.0

        for i in range(len(descricoes)):
            desc = descricoes[i].strip()
            if not desc:
                continue  # Pula linhas vazias

            try:
                qtd = float(quantidades[i].replace(',', '.')) if i < len(quantidades) else 1.0
                if qtd <= 0:
                    qtd = 1.0
            except (ValueError, TypeError):
                qtd = 1.0

            try:
                val = float(valores_unitarios[i].replace(',', '.')) if i < len(valores_unitarios) else 0.0
                if val < 0:
                    val = 0.0
            except (ValueError, TypeError):
                val = 0.0

            tipo = tipos[i] if i < len(tipos) and tipos[i] in ['peca', 'servico'] else 'peca'

            subtotal = qtd * val
            valor_total_calculado += subtotal

            itens_a_criar.append(ItemVenda(
                descricao=desc,
                quantidade=qtd,
                valor_unitario=val,
                tipo=tipo
            ))

        if not itens_a_criar:
            flash('Adicione ao menos um item válido na venda!', 'error')
            return render_template(
                'vendas/form.html',
                clientes=clientes,
                ordens=ordens,
                formas_pagamento=FORMAS_PAGAMENTO_LISTA,
                cliente_preselecionado=cliente_id_val,
                os_preselecionada=os_id_val
            )

        numero = gerar_numero_venda()

        nova_venda = Venda(
            numero=numero,
            cliente_id=cliente_id_val,
            ordem_servico_id=os_id_val,
            data=datetime.now(),
            valor_total=valor_total_calculado,
            forma_pagamento=forma_pagamento,
            status=status,
            observacoes=observacoes
        )
        nova_venda.itens = itens_a_criar

        # Regra de negócio: se vinculada a uma O.S., somar o valor no campo valor_pecas da O.S.
        if os_id_val:
            os_vinculada = db.session.get(OrdemServico, os_id_val)
            if os_vinculada:
                os_vinculada.valor_pecas = (os_vinculada.valor_pecas or 0.0) + valor_total_calculado

        db.session.add(nova_venda)
        db.session.commit()

        flash(f'Venda {nova_venda.numero} registrada com sucesso no valor de {format_currency(valor_total_calculado)}!', 'success')
        return redirect(url_for('vendas_detalhe', id=nova_venda.id))

    # Pré-seleções via query string (?cliente_id=X&os_id=Y)
    cliente_pre = request.args.get('cliente_id', type=int)
    os_pre = request.args.get('os_id', type=int)

    # Se informou O.S., obtém o cliente correspondente
    if os_pre and not cliente_pre:
        os_ref = db.session.get(OrdemServico, os_pre)
        if os_ref:
            cliente_pre = os_ref.cliente_id

    return render_template(
        'vendas/form.html',
        clientes=clientes,
        ordens=ordens,
        formas_pagamento=FORMAS_PAGAMENTO_LISTA,
        cliente_preselecionado=cliente_pre,
        os_preselecionada=os_pre
    )


@app.route('/vendas/<int:id>')
def vendas_detalhe(id):
    """Visualização dos detalhes de uma venda e seus itens."""
    venda = db.get_or_404(Venda, id)
    return render_template('vendas/detalhe.html', venda=venda)


@app.route('/vendas/<int:id>/excluir', methods=['POST'])
def vendas_excluir(id):
    """Exclui uma venda. Se vinculada a uma O.S., desconta o valor correspondente do campo valor_pecas."""
    venda = db.get_or_404(Venda, id)

    # Se estiver vinculada a uma O.S., reverte a soma do valor_pecas
    if venda.ordem_servico_id:
        os_vinculada = db.session.get(OrdemServico, venda.ordem_servico_id)
        if os_vinculada:
            os_vinculada.valor_pecas = max(0.0, (os_vinculada.valor_pecas or 0.0) - (venda.valor_total or 0.0))

    num = venda.numero
    db.session.delete(venda)
    db.session.commit()
    flash(f'Venda {num} excluída com sucesso.', 'success')
    return redirect(url_for('vendas_lista'))


# ==============================================================================
# INICIALIZAÇÃO DO BANCO DE DADOS E CARGA DE DADOS INICIAIS DE DEMONSTRAÇÃO
# ==============================================================================

def popular_dados_iniciais():
    """Insere alguns dados de teste para demonstração inicial se o banco estiver vazio."""
    if Cliente.query.first():
        return  # Já possui dados

    # 1. Clientes de exemplo
    c1 = Cliente(
        nome="Lucas Andrade Silva",
        cpf_cnpj="123.456.789-00",
        telefone="(11) 98765-4321",
        email="lucas.andrade@email.com",
        endereco="Av. Paulista, 1000 - Bela Vista, São Paulo/SP",
        observacoes="Cliente preferencial, contato via WhatsApp.",
        criado_em=datetime.now()
    )
    c2 = Cliente(
        nome="Mariana Costa Fernandes",
        cpf_cnpj="987.654.321-11",
        telefone="(11) 99123-8877",
        email="mariana.costa@empresa.com.br",
        endereco="Rua Augusta, 450 - Consolação, São Paulo/SP",
        observacoes="Empresa de design, requer nota fiscal.",
        criado_em=datetime.now()
    )
    c3 = Cliente(
        nome="Tech Solutions Comércio Ltda",
        cpf_cnpj="12.345.678/0001-99",
        telefone="(11) 3322-1100",
        email="contato@techsolutions.com",
        endereco="Rua Funchal, 200 - Vila Olímpia, São Paulo/SP",
        observacoes="Contrato de manutenção para 15 computadores.",
        criado_em=datetime.now()
    )

    db.session.add_all([c1, c2, c3])
    db.session.commit()

    # 2. Ordens de Serviço de exemplo
    os1 = OrdemServico(
        numero=gerar_numero_os(),
        cliente_id=c1.id,
        tipo_equipamento="Smartphone",
        marca="Apple",
        modelo="iPhone 13 Pro 128GB",
        numero_serie="DNPTL890N6HK",
        senha_equipamento="123456",
        problema="Tela frontal trincada após queda e bateria descarregando rapidamente.",
        diagnostico="Substituição da tela OLED frontal e substituição da bateria original.",
        status="Em reparo",
        tecnico="Carlos Roberto",
        data_abertura=datetime.now(),
        data_previsao=date.today(),
        valor_mao_obra=180.0,
        valor_pecas=0.0
    )
    db.session.add(os1)
    db.session.commit()

    os2 = OrdemServico(
        numero=gerar_numero_os(),
        cliente_id=c2.id,
        tipo_equipamento="Notebook",
        marca="Dell",
        modelo="Inspiron 15 5510",
        numero_serie="BFC89J2",
        senha_equipamento="sem senha",
        problema="Não liga ao pressionar botão power. LED do conector pisca em laranja.",
        diagnostico="Curto-circuito na linha secundária de 3.3V na placa-mãe.",
        status="Aberto",
        tecnico="Carlos Roberto",
        data_abertura=datetime.now(),
        valor_mao_obra=350.0,
        valor_pecas=0.0
    )
    db.session.add(os2)
    db.session.commit()

    os3 = OrdemServico(
        numero=gerar_numero_os(),
        cliente_id=c3.id,
        tipo_equipamento="Notebook",
        marca="Lenovo",
        modelo="ThinkPad T14 Gen 2",
        numero_serie="PF20XK99",
        senha_equipamento="admin2026",
        problema="Lentidão extrema e superaquecimento durante reuniões no Teams.",
        diagnostico="Pasta térmica ressecada, poeira no cooler e SSD SATA precisando de upgrade para NVMe.",
        status="Pronto",
        tecnico="Marcos Paulo",
        data_abertura=datetime.now(),
        data_conclusao=datetime.now(),
        valor_mao_obra=150.0,
        valor_pecas=0.0
    )
    db.session.add(os3)
    db.session.commit()

    # 3. Venda vinculada à OS 1
    venda1 = Venda(
        numero=gerar_numero_venda(),
        cliente_id=c1.id,
        ordem_servico_id=os1.id,
        data=datetime.now(),
        valor_total=720.0,
        forma_pagamento="PIX",
        status="Pago",
        observacoes="Peças aplicadas na O.S. " + os1.numero
    )
    item1 = ItemVenda(
        descricao="Tela OLED iPhone 13 Pro Premium",
        quantidade=1,
        valor_unitario=520.0,
        tipo="peca"
    )
    item2 = ItemVenda(
        descricao="Bateria Original iPhone 13 Pro",
        quantidade=1,
        valor_unitario=200.0,
        tipo="peca"
    )
    venda1.itens = [item1, item2]

    # Atualiza o valor_pecas na OS 1
    os1.valor_pecas = 720.0
    db.session.add(venda1)
    db.session.commit()

    # 4. Venda avulsa paga
    venda2 = Venda(
        numero=gerar_numero_venda(),
        cliente_id=c2.id,
        ordem_servico_id=None,
        data=datetime.now(),
        valor_total=190.0,
        forma_pagamento="Cartão de Crédito",
        status="Pago",
        observacoes="Venda de acessórios na loja."
    )
    item3 = ItemVenda(
        descricao="Fonte Carregador USB-C 65W GaN Universal",
        quantidade=1,
        valor_unitario=140.0,
        tipo="peca"
    )
    item4 = ItemVenda(
        descricao="Cabo USB-C Trançado Reforçado 2m",
        quantidade=1,
        valor_unitario=50.0,
        tipo="peca"
    )
    venda2.itens = [item3, item4]
    db.session.add(venda2)
    db.session.commit()


# Cria as tabelas do banco automaticamente na inicialização
with app.app_context():
    db.create_all()
    popular_dados_iniciais()


if __name__ == '__main__':
    # Inicializa servidor local na porta 5000
    app.run(debug=True, host='0.0.0.0', port=5000)
