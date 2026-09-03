import re
import datetime
import dateutil.relativedelta
import streamlit as st
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Date, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ---------------------------------------------------------
# FUNÇÃO DE VALIDAÇÃO DE CPF
# ---------------------------------------------------------
def validar_cpf(cpf: str) -> bool:
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
        
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = (soma * 10) % 11
    digito1 = 0 if resto == 10 else resto
    if int(cpf[9]) != digito1:
        return False
        
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = (soma * 10) % 11
    digito2 = 0 if resto == 10 else resto
    if int(cpf[10]) != digito2:
        return False
        
    return True

# ---------------------------------------------------------
# 1. BANCO DE DADOS E MODELOS
# ---------------------------------------------------------
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    cpf = Column(String(14), unique=True, nullable=False)
    
    accounts = relationship("BankAccount", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("CreditCard", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    investments = relationship("Investment", back_populates="user", cascade="all, delete-orphan")

class BankAccount(Base):
    __tablename__ = 'bank_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    bank_name = Column(String(50), nullable=False)
    initial_balance = Column(Float, default=0.0)
    
    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")

class CreditCard(Base):
    __tablename__ = 'credit_cards'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    card_name = Column(String(50), nullable=False)
    credit_limit = Column(Float, default=0.0)
    due_day = Column(Integer, default=10, nullable=False)
    closing_days_before = Column(Integer, default=7, nullable=False)
    
    user = relationship("User", back_populates="cards")
    transactions = relationship("Transaction", back_populates="card")

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)

class Transaction(Base):
    __tablename__ = 'transactions'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    account_id = Column(Integer, ForeignKey('bank_accounts.id'), nullable=True)
    card_id = Column(Integer, ForeignKey('credit_cards.id'), nullable=True)
    category_name = Column(String(50), nullable=False)
    description = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    purchase_date = Column(Date, default=datetime.date.today)
    date = Column(Date, default=datetime.date.today)
    trans_type = Column(String(20), nullable=False)
    method = Column(String(50), nullable=False)
    is_paid = Column(Boolean, default=False, nullable=False)
    
    user = relationship("User", back_populates="transactions")
    account = relationship("BankAccount", back_populates="transactions")
    card = relationship("CreditCard", back_populates="transactions")

class Investment(Base):
    __tablename__ = 'investments'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    bank_name = Column(String(50), nullable=False)
    product_name = Column(String(100), nullable=False)
    balance = Column(Float, default=0.0, nullable=False)
    yield_rate = Column(String(50), nullable=False)
    
    user = relationship("User", back_populates="investments")

engine = create_engine('sqlite:///financas_familia.db', connect_args={"check_same_thread": False})

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE credit_cards ADD COLUMN due_day INTEGER DEFAULT 10 NOT NULL;"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE credit_cards ADD COLUMN closing_days_before INTEGER DEFAULT 7 NOT NULL;"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE transactions ADD COLUMN is_paid BOOLEAN DEFAULT 0 NOT NULL;"))
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE transactions ADD COLUMN purchase_date DATE;"))
        conn.execute(text("UPDATE transactions SET purchase_date = date WHERE purchase_date IS NULL;"))
    except Exception:
        pass
    conn.commit()

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    return SessionLocal()

def init_categories(db):
    categorias_padrao = [
        ("Alimentação & Mercado", "Saída"),
        ("Moradia (Aluguel/Condomínio/IPTU)", "Saída"),
        ("Serviços Públicos (Água/Luz/Gás)", "Saída"),
        ("Transporte & Combustível", "Saída"),
        ("Sergio Pessoal", "Saída"),
        ("Patricia Pessoal", "Saída"),
        ("Lazer & Restaurantes", "Saída"),
        ("Saúde & Farmácia", "Saída"),
        ("Assinaturas & Streaming", "Saída"),
        ("Despesas Veiculo", "Saída"),
        ("Despesas com PETs", "Saída"),
        ("Vestuários/Calçados", "Saída"),
        ("Educação & Cursos", "Saída"),
        ("Moveis/Eletro/Eletronicos", "Saída"),
        ("Manutenção Residencial", "Saída"),
        ("Obras e Serviços", "Saída"),
        ("Férias & Viagens", "Saída"),
        ("Festas e Presentes", "Saída"),
        ("Empréstimos & Recebíveis", "Saída"),
        ("Pagamento de Fatura de Cartão", "Saída"),
        ("Outras Despesas", "Saída"),
        ("Salário / Pró-labore", "Entrada"),
        ("Investimentos & Rendimentos", "Entrada"),
        ("Vendas & Extra", "Entrada"),
        ("Outras Receitas", "Entrada")
    ]
    
    existing_cats = {c.name for c in db.query(Category).all()}
    for name, c_type in categorias_padrao:
        if name not in existing_cats:
            db.add(Category(name=name, type=c_type))
    db.commit()


def calcular_data_vencimento_fatura(card, data_ref):
    if data_ref is None:
        return datetime.date.today()

    dia_fechamento = card.due_day - card.closing_days_before
    if dia_fechamento <= 0:
        dia_fechamento += 30

    if data_ref.day >= dia_fechamento:
        return data_ref + dateutil.relativedelta.relativedelta(months=1)
    return data_ref


def aplicar_pagamento_fatura(fatura_items, valor_pagamento):
    valor_restante = float(valor_pagamento)
    itens_pagos = []

    for item in sorted(fatura_items, key=lambda t: (t.date or t.purchase_date or datetime.date.min, t.id)):
        if valor_restante <= 0:
            break

        if float(item.amount) <= valor_restante:
            item.is_paid = True
            valor_restante -= float(item.amount)
            itens_pagos.append(item)
        else:
            break

    return valor_restante, itens_pagos

# ---------------------------------------------------------
# 2. CONFIGURAÇÃO E ESTILIZAÇÃO
# ---------------------------------------------------------
st.set_page_config(
    page_title="Gestão Financeira Familiar", 
    page_icon="💻", 
    layout="wide"
)

st.markdown("""
    <style>
    .stApp {
        background-color: #f8fafc;
    }
    
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
    }

    div[data-testid="stMetric"], .stExpander, div[data-testid="stForm"] {
        background-color: #ffffff;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        box-shadow: 0px 2px 8px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid #e2e8f0 !important;
        margin-bottom: 12px;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
        color: #64748b !important;
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.5rem !important;
        font-weight: 700;
        color: #0f172a;
    }

    .stButton > button, .stDownloadButton > button {
        border-radius: 8px !important;
        background-color: #2563eb;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.5rem 1.2rem;
        transition: all 0.2s ease-in-out;
    }
    
    .stButton > button:hover {
        background-color: #1d4ed8;
        color: white;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 10px;
    }

    .stTabs [data-baseweb="tab"] {
        border-radius: 6px;
        padding: 8px 16px;
        background-color: transparent;
        font-size: 14px;
        font-weight: 600;
    }

    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        color: #2563eb !important;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

if "active_user_id" not in st.session_state:
    st.session_state.active_user_id = None

if "ultima_data_lancamento" not in st.session_state:
    st.session_state.ultima_data_lancamento = datetime.date.today()

if "ultimo_cartao_index" not in st.session_state:
    st.session_state.ultimo_cartao_index = 0

if "ultima_conta_index" not in st.session_state:
    st.session_state.ultima_conta_index = 0

db = get_db()
init_categories(db)

# ---------------------------------------------------------
# 3. BARRA LATERAL: SELEÇÃO DE USUÁRIO
# ---------------------------------------------------------
st.sidebar.title("👨‍👩‍👧‍👦 Família & Acesso")

users = db.query(User).all()
total_users = len(users)

st.sidebar.write(f"**Usuários cadastrados:** {total_users} / 6")

if users:
    user_opts = {f"{u.name} (CPF: {u.cpf})": u.id for u in users}
    selected_label = st.sidebar.selectbox("Alternar usuário ativo:", list(user_opts.keys()))
    st.session_state.active_user_id = user_opts[selected_label]
else:
    st.sidebar.info("Nenhum usuário cadastrado.")

st.sidebar.markdown("---")
st.sidebar.subheader("➕ Adicionar Integrante")

if total_users < 6:
    with st.sidebar.form("form_add_user", clear_on_submit=True):
        new_name = st.text_input("Nome:")
        new_email = st.text_input("E-mail:")
        new_cpf = st.text_input("CPF:", max_chars=14, placeholder="000.000.000-00")
        submit_user = st.form_submit_button("Cadastrar Usuário")
        
        if submit_user:
            if new_name and new_email and new_cpf:
                if not validar_cpf(new_cpf):
                    st.sidebar.error("❌ CPF inválido!")
                else:
                    try:
                        cpf_limpo = re.sub(r'\D', '', new_cpf)
                        cpf_formatado = f"{cpf_limpo[:3]}.{cpf_limpo[3:6]}.{cpf_limpo[6:9]}-{cpf_limpo[9:]}"
                        
                        new_u = User(name=new_name, email=new_email, cpf=cpf_formatado)
                        db.add(new_u)
                        db.commit()
                        st.sidebar.success(f"Usuário {new_name} criado!")
                        st.rerun()
                    except Exception:
                        db.rollback()
                        st.sidebar.error("E-mail ou CPF já cadastrado!")
            else:
                st.sidebar.warning("Preencha todos os campos.")
else:
    st.sidebar.warning("⚠️ Limite de 6 usuários atingido!")

# ---------------------------------------------------------
# 4. CONTEÚDO PRINCIPAL
# ---------------------------------------------------------
st.title("💻 Dashboard Financeiro")

if not st.session_state.active_user_id:
    st.warning("Cadastre ou selecione um usuário na barra lateral para começar.")
    st.stop()

current_user = db.query(User).filter(User.id == st.session_state.active_user_id).first()
st.caption(f"👤 Usuário ativo: **{current_user.name}**")

tab_visao_geral, tab_dashboard, tab_saldos, tab_faturas, tab_lancamentos = st.tabs([
    "🏠 Perfil & Configurações",
    "📊 Dashboard", 
    "🏦 Saldos", 
    "💳 Faturas", 
    "💸 Lançamentos"
])

# =========================================================
# ABA 1: VISÃO GERAL / PERFIL
# =========================================================
with tab_visao_geral:
    st.markdown("### 📋 Resumo do Perfil")
    
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()
    user_investments = db.query(Investment).filter(Investment.user_id == current_user.id).all()

    col_inv, col_cfg = st.columns([1, 1], gap="large")

    with col_inv:
        st.markdown("### 📈 Aplicações & Investimentos")
        if user_investments:
            total_investido = sum(inv.balance for inv in user_investments)
            st.metric("💰 Total Investido", f"R$ {total_investido:,.2f}")
            
            df_inv = pd.DataFrame([{
                "ID": inv.id,
                "Banco / Corretora": inv.bank_name,
                "Produto": inv.product_name,
                "Saldo Atual (R$)": float(inv.balance),
                "Rentabilidade": inv.yield_rate
            } for inv in user_investments])
            
            edited_inv_df = st.data_editor(
                df_inv,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "Banco / Corretora": st.column_config.TextColumn("Banco"),
                    "Produto": st.column_config.TextColumn("Produto"),
                    "Saldo Atual (R$)": st.column_config.NumberColumn("Saldo", format="R$ %.2f", min_value=0.0),
                    "Rentabilidade": st.column_config.TextColumn("Rentab.")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_investimentos"
            )

            if st.button("💾 Salvar Aplicações"):
                for _, row in edited_inv_df.iterrows():
                    inv_db = db.query(Investment).filter(Investment.id == int(row["ID"])).first()
                    if inv_db:
                        inv_db.bank_name = str(row["Banco / Corretora"])
                        inv_db.product_name = str(row["Produto"])
                        inv_db.balance = float(row["Saldo Atual (R$)"])
                        inv_db.yield_rate = str(row["Rentabilidade"])
                db.commit()
                st.success("Aplicações atualizadas!")
                st.rerun()
        else:
            st.info("Nenhuma aplicação cadastrada.")

        with st.expander("➕ Cadastrar / Excluir Aplicação"):
            st.markdown("#### Adicionar Aplicação")
            with st.form("form_add_inv", clear_on_submit=True):
                c1, c2 = st.columns(2)
                inv_bank = c1.text_input("Banco / Corretora:", placeholder="Ex: XP, Nubank")
                inv_product = c2.text_input("Produto:", placeholder="Ex: CDB, Tesouro")
                inv_balance = c1.number_input("Saldo Aplicado (R$):", min_value=0.0, step=100.0)
                inv_yield = c2.text_input("Rentabilidade:", placeholder="Ex: 100% CDI")
                
                submit_inv = st.form_submit_button("Salvar Aplicação")
                if submit_inv:
                    if inv_bank and inv_product:
                        new_inv = Investment(
                            user_id=current_user.id,
                            bank_name=inv_bank,
                            product_name=inv_product,
                            balance=inv_balance,
                            yield_rate=inv_yield
                        )
                        db.add(new_inv)
                        db.commit()
                        st.success("Aplicação cadastrada!")
                        st.rerun()
                    else:
                        st.error("Preencha Banco e Produto.")

            st.markdown("---")
            st.markdown("#### Excluir Aplicação")
            if user_investments:
                inv_dict = {f"#{inv.id} - {inv.bank_name} ({inv.product_name})": inv.id for inv in user_investments}
                sel_inv_del = st.selectbox("Selecione para excluir:", list(inv_dict.keys()), key="sel_del_inv")
                if st.button("🗑️ Excluir Aplicação"):
                    inv_to_del = db.query(Investment).filter(Investment.id == inv_dict[sel_inv_del]).first()
                    if inv_to_del:
                        db.delete(inv_to_del)
                        db.commit()
                        st.success("Aplicação removida!")
                        st.rerun()

    with col_cfg:
        st.markdown("### ⚙️ Contas e Cartões")

        st.markdown("#### 🏦 Contas Correntes")
        acc_count = len(user_accounts)
        st.write(f"**Contas:** {acc_count} / 10")

        if user_accounts:
            df_acc = pd.DataFrame([{
                "ID": a.id,
                "Banco / Conta": a.bank_name,
                "Saldo Inicial (R$)": float(a.initial_balance)
            } for a in user_accounts])
            
            edited_acc_df = st.data_editor(
                df_acc,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "Banco / Conta": st.column_config.TextColumn("Conta"),
                    "Saldo Inicial (R$)": st.column_config.NumberColumn("Saldo Inicial", format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True,
                key="editor_contas"
            )

            if st.button("💾 Salvar Contas"):
                for _, row in edited_acc_df.iterrows():
                    acc_db = db.query(BankAccount).filter(BankAccount.id == int(row["ID"])).first()
                    if acc_db:
                        acc_db.bank_name = str(row["Banco / Conta"])
                        acc_db.initial_balance = float(row["Saldo Inicial (R$)"])
                db.commit()
                st.success("Contas atualizadas!")
                st.rerun()

        if acc_count < 10:
            with st.expander("➕ Nova Conta"):
                with st.form("form_add_acc", clear_on_submit=True):
                    c_bank, c_bal = st.columns(2)
                    bank_name = c_bank.text_input("Nome do Banco / Conta:")
                    initial_balance = c_bal.number_input("Saldo Inicial (R$):", value=0.0, step=50.0)
                    submit_acc = st.form_submit_button("Salvar Conta")
                    
                    if submit_acc and bank_name:
                        new_acc = BankAccount(user_id=current_user.id, bank_name=bank_name, initial_balance=initial_balance)
                        db.add(new_acc)
                        db.commit()
                        st.success("Conta adicionada!")
                        st.rerun()

        st.markdown("---")
        st.markdown("#### 💳 Cartões de Crédito")
        card_count = len(user_cards)
        st.write(f"**Cartões:** {card_count} / 10")

        if user_cards:
            df_cards = pd.DataFrame([{
                "ID": c.id,
                "Cartão": c.card_name,
                "Limite Total (R$)": float(c.credit_limit),
                "Dia Venc.": int(c.due_day),
                "Dias Fech.": int(c.closing_days_before)
            } for c in user_cards])

            edited_cards_df = st.data_editor(
                df_cards,
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "Cartão": st.column_config.TextColumn("Cartão"),
                    "Limite Total (R$)": st.column_config.NumberColumn("Limite", format="R$ %.2f", min_value=0.0),
                    "Dia Venc.": st.column_config.NumberColumn("Venc.", min_value=1, max_value=31),
                    "Dias Fech.": st.column_config.NumberColumn("Fech.", min_value=1, max_value=25)
                },
                hide_index=True,
                use_container_width=True,
                key="editor_cartoes"
            )

            if st.button("💾 Salvar Cartões"):
                for _, row in edited_cards_df.iterrows():
                    card_db = db.query(CreditCard).filter(CreditCard.id == int(row["ID"])).first()
                    if card_db:
                        card_db.card_name = str(row["Cartão"])
                        card_db.credit_limit = float(row["Limite Total (R$)"])
                        card_db.due_day = int(row["Dia Venc."])
                        card_db.closing_days_before = int(row["Dias Fech."])
                db.commit()
                st.success("Cartões atualizados!")
                st.rerun()

        if card_count < 10:
            with st.expander("➕ Novo Cartão"):
                with st.form("form_add_card", clear_on_submit=True):
                    c_name, c_lim = st.columns(2)
                    card_name = c_name.text_input("Nome/Bandeira:")
                    credit_limit = c_lim.number_input("Limite Total (R$):", value=1000.0, step=100.0)
                    
                    col_venc, col_fech = st.columns(2)
                    with col_venc:
                        due_day = st.number_input("Dia Venc.:", min_value=1, max_value=31, value=10)
                    with col_fech:
                        closing_days = st.number_input("Dias Fech.:", min_value=1, max_value=20, value=7)
                    
                    submit_card = st.form_submit_button("Salvar Cartão")
                    if submit_card and card_name:
                        new_card = CreditCard(
                            user_id=current_user.id, 
                            card_name=card_name, 
                            credit_limit=credit_limit,
                            due_day=due_day,
                            closing_days_before=closing_days
                        )
                        db.add(new_card)
                        db.commit()
                        st.success("Cartão adicionado!")
                        st.rerun()

# =========================================================
# ABA 2: DASHBOARD
# =========================================================
with tab_dashboard:
    st.markdown("### 📊 Indicadores Financeiros")
    
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()
    user_investments = db.query(Investment).filter(Investment.user_id == current_user.id).all()
    
    # Filtro que remove "Pagamento de Fatura de Cartão" para evitar dupla contagem
    all_transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id,
        Transaction.category_name != "Pagamento de Fatura de Cartão"
    ).all()

    total_saldo_contas = 0.0
    total_entradas = 0.0
    total_saidas_pagas = 0.0
    total_despesas_pendentes = 0.0

    for acc in user_accounts:
        trans_acc = [t for t in all_transactions if t.account_id == acc.id]
        ent = sum(t.amount for t in trans_acc if t.trans_type == "Entrada" and t.is_paid)
        sai_paga = sum(t.amount for t in trans_acc if t.trans_type == "Saída" and t.is_paid)
        sai_pend = sum(t.amount for t in trans_acc if t.trans_type == "Saída" and not t.is_paid)
        
        saldo_atual = acc.initial_balance + ent - sai_paga
        
        total_saldo_contas += saldo_atual
        total_entradas += ent
        total_saidas_pagas += sai_paga
        total_despesas_pendentes += sai_pend

    total_investimentos = sum(inv.balance for inv in user_investments) if user_investments else 0.0
    patrimonio_liquido_total = total_saldo_contas + total_investimentos

    hoje = datetime.date.today()
    total_faturas_mes = 0.0

    for c in user_cards:
        trans_card = [t for t in all_transactions if t.card_id == c.id and not t.is_paid]

        for t in trans_card:
            ref_date = t.date or t.purchase_date
            venc = calcular_data_vencimento_fatura(c, ref_date)

            if venc.month == hoje.month and venc.year == hoje.year:
                total_faturas_mes += t.amount

    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5, kpi_col6 = st.columns(6)
    kpi_col1.metric("💎 Patrimônio", f"R$ {patrimonio_liquido_total:,.2f}")
    kpi_col2.metric("🏦 Saldo Contas", f"R$ {total_saldo_contas:,.2f}")
    kpi_col3.metric("📈 Aplicações", f"R$ {total_investimentos:,.2f}")
    kpi_col4.metric("🟢 Entradas", f"R$ {total_entradas:,.2f}")
    kpi_col5.metric("🔴 Saídas Pagas", f"R$ {total_saidas_pagas:,.2f}")
    kpi_col6.metric("⚠️ Pendências", f"R$ {(total_despesas_pendentes + total_faturas_mes):,.2f}")

    st.markdown("---")

    col_charts_left, col_charts_right = st.columns([1, 1], gap="large")

    with col_charts_left:
        st.markdown("### 📈 Receitas vs. Patrimônio")
        df_rec_pat = pd.DataFrame([
            {"Métrica": "Receitas (Entradas)", "Valor (R$)": total_entradas},
            {"Métrica": "Patrimônio Total", "Valor (R$)": patrimonio_liquido_total}
        ])
        
        fig_rec_pat = px.bar(
            df_rec_pat,
            x="Métrica",
            y="Valor (R$)",
            color="Métrica",
            text_auto=",.2f",
            color_discrete_sequence=["#10b981", "#8b5cf6"]
        )
        fig_rec_pat.update_layout(showlegend=False, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig_rec_pat, use_container_width=True)

        despesas_nao_pagas = [t for t in all_transactions if t.trans_type == "Saída" and not t.is_paid and t.account_id is not None]
        if despesas_nao_pagas:
            st.markdown("#### 📋 Contas Pendentes a Pagar")
            df_nao_pagas = pd.DataFrame([{
                "Vencimento": t.date,
                "Conta": t.account.bank_name if t.account else "-",
                "Descrição": t.description,
                "Valor (R$)": t.amount
            } for t in despesas_nao_pagas])
            
            st.dataframe(
                df_nao_pagas,
                column_config={
                    "Vencimento": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )

    with col_charts_right:
        st.markdown("### 🍕 Gastos por Categoria")
        gastos_trans = [t for t in all_transactions if t.trans_type == "Saída"]
        
        if gastos_trans:
            cat_totals = {}
            for t in gastos_trans:
                cat_totals[t.category_name] = cat_totals.get(t.category_name, 0.0) + t.amount
            
            total_despesas_geral = sum(cat_totals.values())
            
            df_cat = pd.DataFrame([
                {
                    "Categoria": cat,
                    "Valor (R$)": val,
                    "%": (val / total_despesas_geral) * 100
                }
                for cat, val in cat_totals.items()
            ]).sort_values(by="Valor (R$)", ascending=False)

            col_pie, col_tbl = st.columns([1, 1])

            with col_pie:
                fig_cat = px.pie(
                    df_cat, 
                    values="Valor (R$)", 
                    names="Categoria", 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_cat.update_traces(
                    textinfo="percent", 
                    hoverinfo="label+value+percent"
                )
                fig_cat.update_layout(
                    showlegend=False, 
                    margin=dict(l=0, r=0, t=10, b=10)
                )
                st.plotly_chart(fig_cat, use_container_width=True)

            with col_tbl:
                st.dataframe(
                    df_cat,
                    column_config={
                        "Categoria": st.column_config.TextColumn("Categoria"),
                        "Valor (R$)": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                        "%": st.column_config.NumberColumn("% Total", format="%.1f%%")
                    },
                    hide_index=True,
                    use_container_width=True
                )
        else:
            st.info("Nenhuma despesa registrada para exibir o gráfico.")

# =========================================================
# ABA 3: GESTÃO DE SALDOS
# =========================================================
with tab_saldos:
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    
    if not user_accounts:
        st.info("Nenhuma conta corrente cadastrada.")
    else:
        tab_saldos_contas, tab_extrato = st.tabs(["💰 Saldos", "📄 Extrato"])

        with tab_saldos_contas:
            st.markdown("### 🏦 Saldos das Contas")
            saldo_total_geral = 0.0
            saldos_data = []

            for acc in user_accounts:
                trans_acc = db.query(Transaction).filter(Transaction.account_id == acc.id).all()
                
                entradas = sum(t.amount for t in trans_acc if t.trans_type == "Entrada" and t.is_paid)
                saidas_pagas = sum(t.amount for t in trans_acc if t.trans_type == "Saída" and t.is_paid)
                
                saldo_atual = acc.initial_balance + entradas - saidas_pagas
                saldo_total_geral += saldo_atual

                saldos_data.append({
                    "Conta": acc.bank_name,
                    "Inicial": acc.initial_balance,
                    "Entradas": entradas,
                    "Saídas": saidas_pagas,
                    "Atual": saldo_atual
                })

            st.metric(label="💰 Saldo Total Consolidado", value=f"R$ {saldo_total_geral:,.2f}")
            st.markdown("---")

            st.dataframe(
                pd.DataFrame(saldos_data),
                column_config={
                    "Inicial": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Entradas": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Saídas": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Atual": st.column_config.NumberColumn(format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )

        with tab_extrato:
            st.markdown("### 📄 Extrato da Conta Corrente")
            contas_extrato = {f"{acc.bank_name} (ID {acc.id})": acc for acc in user_accounts}
            conta_extrato_label = st.selectbox(
                "Filtrar por conta corrente:",
                list(contas_extrato.keys()),
                key="filtro_conta_extrato"
            )
            conta_extrato = contas_extrato[conta_extrato_label]
            trans_extrato = db.query(Transaction).filter(
                Transaction.user_id == current_user.id,
                Transaction.account_id == conta_extrato.id
            ).order_by(Transaction.date.desc(), Transaction.id.desc()).all()

            if trans_extrato:
                extrato_data = []
                saldo_extrato = conta_extrato.initial_balance
                for transacao in reversed(trans_extrato):
                    valor = transacao.amount if transacao.trans_type == "Entrada" else -transacao.amount
                    if transacao.is_paid:
                        saldo_extrato += valor
                    extrato_data.append({
                        "ID": transacao.id,
                        "Data Compra": transacao.purchase_date or transacao.date,
                        "Data Lançamento": transacao.date or transacao.purchase_date,
                        "Tipo": transacao.trans_type,
                        "Descrição": transacao.description,
                        "Categoria": transacao.category_name,
                        "Método": transacao.method,
                        "Status": "Pago" if transacao.is_paid else "Pendente",
                        "Valor (R$)": valor,
                        "Saldo (R$)": saldo_extrato
                    })
                extrato_data.reverse()

                entradas_extrato = sum(
                    t.amount for t in trans_extrato
                    if t.trans_type == "Entrada" and t.is_paid
                )
                saidas_extrato = sum(
                    t.amount for t in trans_extrato
                    if t.trans_type == "Saída" and t.is_paid
                )
                col_saldo, col_entradas, col_saidas = st.columns(3)
                col_saldo.metric("Saldo atual", f"R$ {saldo_extrato:,.2f}")
                col_entradas.metric("Entradas pagas", f"R$ {entradas_extrato:,.2f}")
                col_saidas.metric("Saídas pagas", f"R$ {saidas_extrato:,.2f}")

                st.dataframe(
                    pd.DataFrame(extrato_data),
                    column_config={
                        "ID": st.column_config.NumberColumn(disabled=True),
                        "Data Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
                        "Data Lançamento": st.column_config.DateColumn(format="DD/MM/YYYY"),
                        "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Saldo (R$)": st.column_config.NumberColumn(format="R$ %.2f")
                    },
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("Nenhum lançamento registrado nesta conta.")

# =========================================================
# ABA 4: FATURAS DE CARTÃO DE CRÉDITO
# =========================================================
with tab_faturas:
    st.markdown("### 💳 Faturas de Cartão")
    
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    
    if not user_cards:
        st.info("Nenhum cartão cadastrado.")
    else:
        col_sel_card, col_sel_m, col_sel_a = st.columns([2, 1, 1])
        
        card_dict = {c.card_name: c for c in user_cards}
        with col_sel_card:
            sel_card_name = st.selectbox("Cartão:", list(card_dict.keys()))
            sel_card = card_dict[sel_card_name]

        with col_sel_m:
            meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            mes_sel = st.selectbox("Mês:", meses, index=datetime.date.today().month - 1)
            mes_venc_num = meses.index(mes_sel) + 1

        with col_sel_a:
            ano_atual = datetime.date.today().year
            ano_venc_num = st.number_input("Ano:", min_value=2020, max_value=2035, value=ano_atual)

        dia_fechamento = sel_card.due_day - sel_card.closing_days_before
        if dia_fechamento <= 0:
            dia_fechamento += 30

        trans_card = db.query(Transaction).filter(
            Transaction.card_id == sel_card.id,
            Transaction.is_paid == False
        ).all()

        fatura_items = []

        for t in trans_card:
            ref_date = t.date or t.purchase_date
            data_vencimento_fatura = calcular_data_vencimento_fatura(sel_card, ref_date)

            if data_vencimento_fatura.month == mes_venc_num and data_vencimento_fatura.year == ano_venc_num:
                fatura_items.append(t)

        total_fatura = sum(t.amount for t in fatura_items)

        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Fatura ({mes_sel}/{ano_venc_num})", f"R$ {total_fatura:,.2f}")
        m2.metric("Vencimento", f"Dia {sel_card.due_day}")
        m3.metric("Fechamento", f"Dia {dia_fechamento}")

        with st.expander("💵 Quitar / Pagar Fatura"):
            if not user_accounts:
                st.warning("Cadastre uma Conta Corrente para registrar o pagamento.")
            elif total_fatura <= 0:
                st.info("Esta fatura não possui lançamentos pendentes.")
            else:
                with st.form("form_pagar_fatura", clear_on_submit=True):
                    cp1, cp2, cp3, cp4 = st.columns(4)
                    acc_pay_dict = {a.bank_name: a.id for a in user_accounts}
                    
                    sel_acc_pay_name = cp1.selectbox("Conta Origem:", list(acc_pay_dict.keys()))
                    valor_pagamento = cp2.number_input(
                        "Valor Pagar (R$):",
                        value=float(total_fatura),
                        min_value=0.01,
                        max_value=float(total_fatura),
                        step=10.0
                    )
                    data_pagamento = cp3.date_input("Data Pagamento:", value=st.session_state.ultima_data_lancamento)
                    metodo_pagamento = cp4.selectbox("Forma:", ["PIX", "Débito Automático", "Boleto / TED"])

                    btn_pagar = st.form_submit_button("Confirmar Pagamento")

                    if btn_pagar:
                        acc_pay_id = acc_pay_dict[sel_acc_pay_name]
                        desc_pagto = f"Pagamento Fatura {sel_card.card_name} ({mes_sel}/{ano_venc_num})"

                        saldo_restante, itens_pagos = aplicar_pagamento_fatura(fatura_items, valor_pagamento)

                        if saldo_restante > 0:
                            st.warning(f"Pagamento parcial aplicado. Restou R$ {saldo_restante:,.2f} da fatura sem quitação.")

                        nova_trans_pagto = Transaction(
                            user_id=current_user.id,
                            account_id=acc_pay_id,
                            category_name="Pagamento de Fatura de Cartão",
                            description=desc_pagto,
                            amount=valor_pagamento,
                            purchase_date=data_pagamento,
                            date=data_pagamento,
                            trans_type="Saída",
                            method=metodo_pagamento,
                            is_paid=True
                        )
                        db.add(nova_trans_pagto)
                        db.commit()
                        st.session_state.ultima_data_lancamento = data_pagamento
                        st.success(f"Pagamento efetuado com sucesso! {len(itens_pagos)} item(ns) marcado(s) como pago(s).")
                        st.rerun()

        st.markdown("#### Lançamentos pendentes na Fatura")
        if fatura_items:
            df_fat = pd.DataFrame([{
                "Data Compra": t.purchase_date or t.date,
                "Descrição": t.description,
                "Categoria": t.category_name,
                "Valor (R$)": t.amount
            } for t in fatura_items])

            st.dataframe(
                df_fat,
                column_config={
                    "Data Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Nenhum lançamento pendente nesta fatura.")

# =========================================================
# ABA 5: LANÇAMENTOS & EDIÇÃO
# =========================================================
with tab_lancamentos:
    st.markdown("### 📝 Novo Lançamento")
    
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()

    if not user_accounts and not user_cards:
        st.info("Cadastre uma Conta ou Cartão de Crédito para realizar lançamentos.")
    else:
        origem = st.radio("Origem do Lançamento:", ["Conta Corrente", "Cartão de Crédito"], horizontal=True)

        if origem == "Conta Corrente":
            if not user_accounts:
                st.warning("Nenhuma conta cadastrada.")
            else:
                acc_idx = min(st.session_state.ultima_conta_index, len(user_accounts) - 1)
                trans_type = st.selectbox("Tipo:", ["Saída", "Entrada"], key="acc_trans_type_sel")

                with st.form("form_trans_acc", clear_on_submit=True):
                    cl1, cl2, cl3, cl4 = st.columns(4)
                    
                    acc_dict = {a.bank_name: (a.id, idx) for idx, a in enumerate(user_accounts)}
                    sel_acc_label = cl1.selectbox("Conta:", list(acc_dict.keys()), index=acc_idx)
                    sel_acc_id, sel_acc_idx = acc_dict[sel_acc_label]
                    
                    cats = db.query(Category).filter(Category.type == trans_type).all()
                    sel_cat = cl2.selectbox("Categoria:", [c.name for c in cats])
                    method = cl3.selectbox("Método:", ["PIX", "Boleto", "TED", "Saque", "Débito Automático", "Outro"])
                    amount = cl4.number_input("Valor (R$):", min_value=0.01, step=10.0)

                    cl5, cl6, cl7 = st.columns([2, 1, 1])
                    desc = cl5.text_input("Descrição:", placeholder="Ex: Aluguel, Mercado")
                    trans_date = cl6.date_input("Data:", value=st.session_state.ultima_data_lancamento)
                    status_pago = cl7.checkbox("Lançamento Pago?", value=True)

                    st.markdown("---")
                    cr1, cr2 = st.columns([1, 3])
                    is_recurring = cr1.checkbox("Recorrente?")
                    qnt_meses = cr2.number_input("Quantidade Meses:", min_value=1, max_value=60, value=12, step=1, disabled=not is_recurring)

                    btn_save_trans = st.form_submit_button("💾 Salvar Lançamento")

                    if btn_save_trans:
                        if desc:
                            total_repeticoes = qnt_meses if is_recurring else 1
                            for i in range(total_repeticoes):
                                data_futura = trans_date + dateutil.relativedelta.relativedelta(months=i)
                                pago_futuro = status_pago if i == 0 else False
                                desc_rec = f"{desc} ({i+1}/{total_repeticoes})" if is_recurring else desc

                                new_t = Transaction(
                                    user_id=current_user.id,
                                    account_id=sel_acc_id,
                                    category_name=sel_cat,
                                    description=desc_rec,
                                    amount=amount,
                                    purchase_date=trans_date,
                                    date=data_futura,
                                    trans_type=trans_type,
                                    method=method,
                                    is_paid=pago_futuro
                                )
                                db.add(new_t)
                            
                            db.commit()
                            st.session_state.ultima_data_lancamento = trans_date
                            st.session_state.ultima_conta_index = sel_acc_idx
                            st.success("Lançamento salvo!")
                            st.rerun()
                        else:
                            st.error("Preencha a descrição.")

        else: # Cartão de Crédito
            if not user_cards:
                st.warning("Nenhum cartão cadastrado.")
            else:
                card_idx = min(st.session_state.ultimo_cartao_index, len(user_cards) - 1)

                with st.form("form_trans_card", clear_on_submit=True):
                    cc1, cc2, cc3 = st.columns(3)
                    
                    card_dict = {f"{c.card_name}": (c, idx) for idx, c in enumerate(user_cards)}
                    sel_card_label = cc1.selectbox("Cartão:", list(card_dict.keys()), index=card_idx)
                    sel_card_obj, sel_card_idx = card_dict[sel_card_label]
                    
                    cats = db.query(Category).filter(Category.type == "Saída").all()
                    sel_cat = cc2.selectbox("Categoria:", [c.name for c in cats])
                    total_amount = cc3.number_input("Valor (R$):", min_value=0.01, step=10.0)
                    
                    cc4, cc5, cc6 = st.columns([2, 1, 1])
                    desc = cc4.text_input("Descrição:", placeholder="Ex: Assinatura Netflix, Mercado")
                    
                    modo_compra = cc5.radio("Tipo de Lançamento:", ["Parcelado", "Recorrente (Mensal)"])
                    purchase_date_input = cc6.date_input("Data Compra:", value=st.session_state.ultima_data_lancamento)

                    st.markdown("---")
                    
                    if modo_compra == "Parcelado":
                        parcelas = st.number_input("Quantidade de Parcelas:", min_value=1, max_value=48, value=1, step=1)
                        valor_parcela = total_amount / parcelas if parcelas > 0 else total_amount
                        st.info(f"💡 **{parcelas}x** de **R$ {valor_parcela:.2f}** (Valor Total: R$ {total_amount:.2f})")
                    else:
                        qnt_meses_card = st.number_input("Repetir por quantos meses?", min_value=1, max_value=60, value=12, step=1)
                        st.info(f"💡 **R$ {total_amount:.2f}** cobrados todos os meses durante **{qnt_meses_card} meses**.")

                    btn_save_card_trans = st.form_submit_button("💾 Salvar no Cartão")

                    if btn_save_card_trans:
                        if desc:
                            if modo_compra == "Parcelado":
                                total_repeticoes = parcelas
                                valor_lancamento = total_amount / parcelas
                            else:
                                total_repeticoes = qnt_meses_card
                                valor_lancamento = total_amount

                            for i in range(total_repeticoes):
                                data_parcela = purchase_date_input + dateutil.relativedelta.relativedelta(months=i)
                                
                                if modo_compra == "Parcelado":
                                    desc_final = f"{desc} ({i+1}/{total_repeticoes})" if total_repeticoes > 1 else desc
                                    metodo_str = f"Cartão ({total_repeticoes}x)" if total_repeticoes > 1 else "Cartão (À vista)"
                                else:
                                    desc_final = f"{desc} (Recorrente {i+1}/{total_repeticoes})"
                                    metodo_str = "Cartão (Recorrente)"

                                new_t = Transaction(
                                    user_id=current_user.id,
                                    card_id=sel_card_obj.id,
                                    category_name=sel_cat,
                                    description=desc_final,
                                    amount=valor_lancamento,
                                    purchase_date=purchase_date_input,
                                    date=data_parcela,
                                    trans_type="Saída",
                                    method=metodo_str,
                                    is_paid=False
                                )
                                db.add(new_t)
                            
                            db.commit()
                            st.session_state.ultima_data_lancamento = purchase_date_input
                            st.session_state.ultimo_cartao_index = sel_card_idx
                            st.success("Lançamento no cartão registrado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Preencha a descrição.")

    st.markdown("---")
    st.markdown("### 📋 Histórico")

    user_trans_query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    all_trans = user_trans_query.order_by(Transaction.date.desc()).all()

    if all_trans:
        with st.expander("🔍 Filtros de Busca"):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                tipo_filter = st.selectbox("Tipo:", ["Todos", "Entrada", "Saída"])
            with col_f2:
                status_filter = st.selectbox("Status:", ["Todos", "Apenas Pagos", "Apenas Pendentes"])
            with col_f3:
                busca_desc = st.text_input("Buscar Descrição:", placeholder="Ex: Aluguel")

        filtered_trans = all_trans
        if tipo_filter != "Todos":
            filtered_trans = [t for t in filtered_trans if t.trans_type == tipo_filter]
            
        if status_filter == "Apenas Pagos":
            filtered_trans = [t for t in filtered_trans if t.is_paid]
        elif status_filter == "Apenas Pendentes":
            filtered_trans = [t for t in filtered_trans if not t.is_paid]
            
        if busca_desc:
            filtered_trans = [t for t in filtered_trans if busca_desc.lower() in t.description.lower()]

        if filtered_trans:
            all_cat_names = [c.name for c in db.query(Category).all()]
            
            data_table = []
            for t in filtered_trans:
                status_str = "🟢 Pago" if t.is_paid else "🟡 Pendente"
                data_table.append({
                    "ID": t.id,
                    "Data Compra": t.purchase_date or t.date,
                    "Data Vencimento": t.date,
                    "Status": status_str,
                    "Categoria": t.category_name,
                    "Descrição": t.description,
                    "Valor (R$)": float(t.amount)
                })

            edited_df = st.data_editor(
                pd.DataFrame(data_table),
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "Data Compra": st.column_config.DateColumn("Data Compra", format="DD/MM/YYYY"),
                    "Data Vencimento": st.column_config.DateColumn("Data Venc/Lanç.", format="DD/MM/YYYY"),
                    "Status": st.column_config.SelectboxColumn("Status", options=["🟢 Pago", "🟡 Pendente"]),
                    "Categoria": st.column_config.SelectboxColumn("Categoria", options=all_cat_names),
                    "Descrição": st.column_config.TextColumn("Descrição"),
                    "Valor (R$)": st.column_config.NumberColumn("Valor", format="R$ %.2f", min_value=0.01)
                },
                hide_index=True,
                use_container_width=True,
                key="editor_lancamentos"
            )

            if st.button("💾 Salvar Tabela"):
                for _, row in edited_df.iterrows():
                    trans_db = db.query(Transaction).filter(Transaction.id == int(row["ID"])).first()
                    if trans_db:
                        trans_db.purchase_date = row["Data Compra"]
                        trans_db.date = row["Data Vencimento"]
                        trans_db.is_paid = True if "Pago" in str(row["Status"]) else False
                        trans_db.category_name = row["Categoria"]
                        trans_db.description = str(row["Descrição"])
                        trans_db.amount = float(row["Valor (R$)"])
                db.commit()
                st.success("Histórico atualizado!")
                st.rerun()

            st.markdown("---")
            with st.expander("🗑️ Excluir Lançamento"):
                trans_dict = {f"ID #{t.id} - {t.description} (R$ {t.amount:.2f})": t for t in filtered_trans}
                selected_trans_label = st.selectbox("Selecione para excluir:", list(trans_dict.keys()))
                selected_trans = trans_dict[selected_trans_label]

                if st.button(f"Confirmar Exclusão do Lançamento #{selected_trans.id}"):
                    db.delete(selected_trans)
                    db.commit()
                    st.success("Excluído com sucesso!")
                    st.rerun()
        else:
            st.warning("Nenhum lançamento encontrado.")
    else:
        st.info("Nenhum lançamento registrado.")

db.close()