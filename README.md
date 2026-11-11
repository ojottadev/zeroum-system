# ZER01 - Sistema de Assistência Técnica

Sistema web completo de **Assistência Técnica** desenvolvido com **Flask**, **SQLite**, **SQLAlchemy** e interface **Mobile-First** moderna estilizada com **Tailwind CSS via CDN** e **FontAwesome 6**.

---

## 🚀 Como Executar

### 1. Pré-requisitos
- Python 3.10 ou superior instalado.

### 2. Instalação e Execução

No terminal, navegue até a pasta do projeto:

```bash
cd /home/jotta/Documentos/zeroum-system
```

Crie o ambiente virtual (se ainda não tiver) e instale as dependências:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Inicie o servidor Flask:

```bash
python app.py
```

O sistema criará as tabelas do SQLite automaticamente caso não existam (`assistencia_tecnica.db`) e já carregará registros de demonstração na primeira inicialização.

Acesse no seu navegador:
👉 **[http://localhost:5000](http://localhost:5000)**

---

## 📁 Estrutura do Projeto

```text
assistencia_tecnica/
├── app.py                     # Aplicação Flask, rotas, regras de negócio e filtros Jinja
├── models.py                  # Modelos de dados SQLAlchemy (Cliente, OrdemServico, Venda, ItemVenda)
├── requirements.txt           # Dependências do projeto (Flask, Flask-SQLAlchemy)
├── test_app.py                # Testes unitários automatizados (100% de aprovação)
├── templates/
│   ├── base.html              # Layout base responsivo com navbar mobile (hamburguer), alertas flash e footer
│   ├── dashboard.html         # Dashboard com cards de métricas (KPIs), O.S. e vendas recentes
│   ├── clientes/
│   │   ├── lista.html         # Listagem com busca (nome, CPF/CNPJ, telefone) e cards responsivos
│   │   ├── form.html          # Cadastro e edição de clientes
│   │   └── detalhe.html       # Perfil completo do cliente e histórico de O.S. e Vendas
│   ├── os/
│   │   ├── lista.html         # Listagem com filtros por status e busca geral (número, cliente, marca, modelo)
│   │   ├── form.html          # Cadastro e edição de O.S.
│   │   └── detalhe.html       # Visualização detalhada da O.S., prazos, financeiro e alteração rápida de status
│   └── vendas/
│       ├── lista.html         # Listagem com busca por número ou cliente
│       ├── form.html          # Cadastro de vendas com itens dinâmicos e cálculo em tempo real
│       └── detalhe.html       # Discriminação detalhada de peças e serviços da venda
└── static/                    # Arquivos estáticos (opcional)
```

---

## 🛠️ Módulos e Regras Implementadas

### 1. Dashboard (`/`)
- **Cards de Métricas (KPIs)**:
  - Quantidade de O.S. abertas (*Aberto*, *Em diagnóstico*, *Aguardando peça*, *Em reparo*).
  - Quantidade de O.S. prontas (*Pronto*).
  - Faturamento do mês atual (vendas com status *"Pago"*).
  - Novos clientes cadastrados no mês atual.
- **Tabelas / Listas Recentes**:
  - 8 Ordens de Serviço mais recentes com status e valores.
  - 5 Vendas mais recentes com método de pagamento e status.
- **Atalhos de Ação Rápida**: Nova O.S., Novo Cliente e Nova Venda.

### 2. Clientes
- `GET /clientes`: Busca em tempo real por nome, CPF/CNPJ ou telefone.
- `GET/POST /clientes/novo`: Cadastro com validação de nome obrigatório.
- `GET/POST /clientes/<id>/editar`: Atualização de informações cadastrais.
- `GET /clientes/<id>`: Histórico completo de equipamentos (O.S.) e histórico de vendas/faturamento.
- `POST /clientes/<id>/excluir`: **Regra de proteção**: Bloqueia exclusão caso o cliente possua O.S. ou Vendas vinculadas.

### 3. Ordens de Serviço (O.S.)
- `GET /os`: Listagem com filtro por status (pílulas de toque rápido e dropdown) e busca (número, cliente, marca, modelo).
- `GET/POST /os/nova`: Geração automática de número no formato `OS-YYYYMMDD-XXX`.
- `GET /os/<id>`: Detalhes do equipamento, laudo técnico, linha do tempo de datas e resumo financeiro.
- `GET/POST /os/<id>/editar`: Edição de informações e valores.
- `POST /os/<id>/status`: Atualização rápida de status.
- **Regras de Ciclo de Vida**:
  - Ao mudar para **"Pronto"**, preenche automaticamente a `data_conclusao` se estiver vazia.
  - Ao mudar para **"Entregue"**, preenche automaticamente `data_entrega` e `data_conclusao` se estiverem vazias.

### 4. Vendas & Peças
- `GET /vendas`: Listagem com busca e filtro por status.
- `GET/POST /vendas/nova`:
  - Geração automática de número no formato `VD-YYYYMMDD-XXX`.
  - Múltiplos itens dinâmicos adicionados/removidos via JavaScript.
  - Cálculo automático do `valor_total` em tempo real.
  - **Regra de Negócio**: Se vinculada a uma O.S., soma automaticamente o valor faturado no campo `valor_pecas` da O.S.
- `GET /vendas/<id>`: Discriminação de cada peça ou serviço com quantidade, unitário e subtotal.
- `POST /vendas/<id>/excluir`: Exclui a venda e estorna o valor de `valor_pecas` da O.S. vinculada.

---

## 🎨 Design & Mobile-First
- Construído com classes utilitárias do Tailwind CSS.
- Menu de navegação responsivo com gaveta móvel acionada por botão hambúrguer.
- Badges coloridos específicos para cada status de O.S. e Venda.
- Formulários com campos largos e acessíveis para toque na tela de smartphones.
- Formatação monetária brasileira (`R$ 1.250,00`) e de datas brasileiras (`DD/MM/AAAA`).
