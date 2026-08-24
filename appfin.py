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
        ("Moradia (Aluguel/Condomínio/IPTU)", "Saída"),
        ("Serviços Públicos (Água/Luz/Gás)", "Saída"),
        ("Alimentação & Mercado", "Saída"),
        ("Assinaturas & Streaming", "Saída"),
        ("Saúde & Farmácia", "Saída"),
        ("Transporte & Combustível", "Saída"),
        ("Educação & Cursos", "Saída"),
        ("Lazer & Restaurantes", "Saída"),
        ("Vestuário & Compras", "Saída"),
        ("Obras e Serviços", "Saída"),
        ("Festas e Presentes", "Saída"),
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

# ---------------------------------------------------------
# 2. CONFIGURAÇÃO E SESSÃO DO STREAMLIT
# ---------------------------------------------------------
st.set_page_config(page_title="Gestão Financeira Familiar", layout="wide")

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
# 3. BARRA LATERAL: SELEÇÃO DE USUÁRIO / NOVO USUÁRIO
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
st.title("💰 Gestão Financeira Familiar")

if not st.session_state.active_user_id:
    st.warning("Cadastre ou selecione um usuário na barra lateral para começar.")
    st.stop()

current_user = db.query(User).filter(User.id == st.session_state.active_user_id).first()
st.subheader(f"Painel de: **{current_user.name}** (CPF: {current_user.cpf})")

tab_visao_geral, tab_dashboard, tab_saldos, tab_faturas, tab_lancamentos = st.tabs([
    "🏠 Visão Geral",
    "📊 Dashboard", 
    "🏦 Saldo das Contas", 
    "💳 Faturas dos Cartões", 
    "💸 Lançamentos"
])

# =========================================================
# ABA 1: VISÃO GERAL
# =========================================================
with tab_visao_geral:
    st.markdown("### 📋 Resumo do Perfil & Cadastros")
    
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()
    user_investments = db.query(Investment).filter(Investment.user_id == current_user.id).all()

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
                "Banco / Corretora": st.column_config.TextColumn("Banco / Corretora"),
                "Produto": st.column_config.TextColumn("Produto"),
                "Saldo Atual (R$)": st.column_config.NumberColumn("Saldo Atual (R$)", format="R$ %.2f", min_value=0.0),
                "Rentabilidade": st.column_config.TextColumn("Rentabilidade")
            },
            hide_index=True,
            use_container_width=True,
            key="editor_investimentos"
        )

        if st.button("💾 Salvar Alterações nas Aplicações"):
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
        st.info("Nenhuma aplicação cadastrada ainda.")

    with st.expander("➕ Cadastrar / Excluir Aplicação"):
        col_inv_add, col_inv_del = st.columns(2)
        
        with col_inv_add:
            st.markdown("#### Adicionar Aplicação")
            with st.form("form_add_inv", clear_on_submit=True):
                inv_bank = st.text_input("Banco / Corretora:", placeholder="Ex: XP, Nubank, BTG")
                inv_product = st.text_input("Produto:", placeholder="Ex: CDB, Tesouro Selic, FIIs")
                inv_balance = st.number_input("Saldo Aplicado (R$):", min_value=0.0, step=100.0)
                inv_yield = st.text_input("Rentabilidade:", placeholder="Ex: 100% CDI, 12% a.a., IPCA+6%")
                
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
                        st.error("Preencha o Banco e o Produto.")
                        
        with col_inv_del:
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
            else:
                st.write("Sem aplicações para excluir.")

    st.markdown("---")
    st.markdown("### ⚙️ Gestão de Contas e Cartões")
    col_accounts, col_cards = st.columns(2)

    with col_accounts:
        st.markdown("#### 🏦 Contas Correntes")
        acc_count = len(user_accounts)
        st.write(f"**Contas cadastradas:** {acc_count} / 10")

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
                    "Banco / Conta": st.column_config.TextColumn("Banco / Conta"),
                    "Saldo Inicial (R$)": st.column_config.NumberColumn("Saldo Inicial (R$)", format="R$ %.2f")
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
            with st.expander("➕ Adicionar Nova Conta"):
                with st.form("form_add_acc", clear_on_submit=True):
                    bank_name = st.text_input("Nome do Banco / Conta:")
                    initial_balance = st.number_input("Saldo Inicial (R$):", value=0.0, step=50.0)
                    submit_acc = st.form_submit_button("Salvar Conta")
                    
                    if submit_acc:
                        if bank_name:
                            new_acc = BankAccount(user_id=current_user.id, bank_name=bank_name, initial_balance=initial_balance)
                            db.add(new_acc)
                            db.commit()
                            st.success("Conta adicionada!")
                            st.rerun()

    with col_cards:
        st.markdown("#### 💳 Cartões de Crédito")
        card_count = len(user_cards)
        st.write(f"**Cartões cadastrados:** {card_count} / 10")

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
                    "Limite Total (R$)": st.column_config.NumberColumn("Limite Total (R$)", format="R$ %.2f", min_value=0.0),
                    "Dia Venc.": st.column_config.NumberColumn("Dia Venc.", min_value=1, max_value=31),
                    "Dias Fech.": st.column_config.NumberColumn("Dias Fech.", min_value=1, max_value=25)
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
            with st.expander("➕ Adicionar Novo Cartão"):
                with st.form("form_add_card", clear_on_submit=True):
                    card_name = st.text_input("Nome/Bandeira do Cartão:")
                    credit_limit = st.number_input("Limite Total (R$):", value=1000.0, step=100.0)
                    
                    col_venc, col_fech = st.columns(2)
                    with col_venc:
                        due_day = st.number_input("Dia de Vencimento:", min_value=1, max_value=31, value=10)
                    with col_fech:
                        closing_days = st.number_input("Dias Antes para Fechar:", min_value=1, max_value=20, value=7)
                    
                    submit_card = st.form_submit_button("Salvar Cartão")
                    
                    if submit_card:
                        if card_name:
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
    st.markdown("### 📊 Dashboard & Indicadores Financeiros")
    
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()
    user_investments = db.query(Investment).filter(Investment.user_id == current_user.id).all()
    all_transactions = db.query(Transaction).filter(Transaction.user_id == current_user.id).all()

    accounts_data = []
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
        
        accounts_data.append({"Conta": acc.bank_name, "Saldo Atual": saldo_atual})

    # CÁLCULO DOS INVESTIMENTOS E PATRIMÔNIO LÍQUIDO TOTAL
    total_investimentos = sum(inv.balance for inv in user_investments) if user_investments else 0.0
    patrimonio_liquido_total = total_saldo_contas + total_investimentos

    hoje = datetime.date.today()
    total_faturas_mes = 0.0

    for c in user_cards:
        dia_fechamento = c.due_day - c.closing_days_before
        if dia_fechamento <= 0:
            dia_fechamento += 30
            
        trans_card = [t for t in all_transactions if t.card_id == c.id and not t.is_paid]
        
        for t in trans_card:
            ref_date = t.date or t.purchase_date
            if ref_date.day >= dia_fechamento:
                venc = ref_date + dateutil.relativedelta.relativedelta(months=1)
            else:
                venc = ref_date
                
            if venc.month == hoje.month and venc.year == hoje.year:
                total_faturas_mes += t.amount

    # METRICAS DE PATRIMÔNIO E RECURSOS DISPONÍVEIS
    st.markdown("#### 💎 Patrimônio & Saldos")
    kpi0, kpi1, kpi_inv = st.columns(3)
    kpi0.metric("💎 Patrimônio Total Consolidado", f"R$ {patrimonio_liquido_total:,.2f}")
    kpi1.metric("🏦 Saldo Disponível (Contas)", f"R$ {total_saldo_contas:,.2f}")
    kpi_inv.metric("📈 Total em Aplicações", f"R$ {total_investimentos:,.2f}")

    st.markdown("---")
    st.markdown("#### 💵 Fluxo de Caixa")
    kpi2, kpi3, kpi4 = st.columns(3)
    kpi2.metric("🟢 Entradas Confirmadas", f"R$ {total_entradas:,.2f}")
    kpi3.metric("🔴 Saídas Realizadas (Pagas)", f"R$ {total_saidas_pagas:,.2f}")
    kpi4.metric("📊 Balanço do Período", f"R$ {(total_entradas - total_saidas_pagas):,.2f}")

    st.markdown("---")
    st.markdown("### 🚨 Painel de Despesas Pendentes / Não Pagas")
    
    col_p1, col_p2, col_p3 = st.columns(3)
    col_p1.metric("⏳ Despesas Pendentes (Contas)", f"R$ {total_despesas_pendentes:,.2f}")
    col_p2.metric(f"💳 Faturas Cartão ({hoje.strftime('%m/%Y')})", f"R$ {total_faturas_mes:,.2f}")
    col_p3.metric("⚠️ Total Geral Pendente", f"R$ {(total_despesas_pendentes + total_faturas_mes):,.2f}", delta="-Total a Liquidar", delta_color="inverse")

    despesas_nao_pagas = [t for t in all_transactions if t.trans_type == "Saída" and not t.is_paid and t.account_id is not None]
    
    if despesas_nao_pagas:
        st.markdown("#### 📋 Detalhamento das Contas a Pagar")
        df_nao_pagas = pd.DataFrame([{
            "Vencimento/Data": t.date,
            "Conta Origem": t.account.bank_name if t.account else "-",
            "Categoria": t.category_name,
            "Descrição": t.description,
            "Valor (R$)": t.amount
        } for t in despesas_nao_pagas])
        
        st.dataframe(
            df_nao_pagas,
            column_config={
                "Vencimento/Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.success("🎉 Nenhuma conta pendente ou em atraso registrada!")

    st.markdown("---")
    g_col1, g_col2 = st.columns(2)

    with g_col1:
        if patrimonio_liquido_total > 0:
            df_patrimonio = pd.DataFrame([
                {"Tipo": "Saldo em Conta Corrente", "Valor": total_saldo_contas},
                {"Tipo": "Aplicações & Investimentos", "Valor": total_investimentos}
            ])
            
            df_patrimonio["Percentual"] = (df_patrimonio["Valor"] / patrimonio_liquido_total) * 100
            
            fig_pat = px.pie(
                df_patrimonio,
                values="Valor",
                names="Tipo",
                title="🏛️ Distribuição do Patrimônio Total",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_pat.update_traces(
                textposition='inside', 
                textinfo='percent',
                hovertemplate='%{label}<br>Percentual: %{percent}'
            )
            fig_pat.update_layout(showlegend=False)
            st.plotly_chart(fig_pat, use_container_width=True)
            
            # Tabela Estilo Planilha Alinhada abaixo do Gráfico
            st.dataframe(
                df_patrimonio[["Tipo", "Valor", "Percentual"]],
                column_config={
                    "Tipo": st.column_config.TextColumn("Item / Origem"),
                    "Valor": st.column_config.NumberColumn("Saldo (R$)", format="R$ %.2f"),
                    "Percentual": st.column_config.NumberColumn("Part. (%)", format="%.2f %%")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Cadastre contas correntes ou investimentos para visualizar o gráfico patrimonial.")

    with g_col2:
        gastos_trans = [t for t in all_transactions if t.trans_type == "Saída"]
        if gastos_trans:
            cat_totals = {}
            total_gastos = 0.0
            for t in gastos_trans:
                cat_totals[t.category_name] = cat_totals.get(t.category_name, 0.0) + t.amount
                total_gastos += t.amount
            
            df_cat = pd.DataFrame(list(cat_totals.items()), columns=["Categoria", "Valor"])
            df_cat["Percentual"] = (df_cat["Valor"] / total_gastos) * 100
            df_cat = df_cat.sort_values(by="Valor", ascending=False)
            
            fig_cat = px.pie(
                df_cat, 
                values="Valor", 
                names="Categoria", 
                title="🍕 Total de Gastos por Categoria",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_cat.update_traces(
                textposition='inside', 
                textinfo='percent',
                hovertemplate='%{label}<br>Percentual: %{percent}'
            )
            fig_cat.update_layout(showlegend=False)
            st.plotly_chart(fig_cat, use_container_width=True)
            
            # Tabela Estilo Planilha Alinhada abaixo do Gráfico
            st.dataframe(
                df_cat[["Categoria", "Valor", "Percentual"]],
                column_config={
                    "Categoria": st.column_config.TextColumn("Categoria de Gasto"),
                    "Valor": st.column_config.NumberColumn("Total Gastos (R$)", format="R$ %.2f"),
                    "Percentual": st.column_config.NumberColumn("Part. (%)", format="%.2f %%")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Nenhum gasto registrado para gerar o gráfico.")

# =========================================================
# ABA 3: GESTÃO DE SALDOS
# =========================================================
with tab_saldos:
    st.markdown("### 🏦 Gestão de Saldos das Contas Correntes")
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    
    if not user_accounts:
        st.info("Nenhuma conta corrente cadastrada para este usuário.")
    else:
        saldo_total_geral = 0.0
        saldos_data = []

        for acc in user_accounts:
            trans_acc = db.query(Transaction).filter(Transaction.account_id == acc.id).all()
            
            entradas = sum(t.amount for t in trans_acc if t.trans_type == "Entrada" and t.is_paid)
            saidas_pagas = sum(t.amount for t in trans_acc if t.trans_type == "Saída" and t.is_paid)
            saidas_pendentes = sum(t.amount for t in trans_acc if t.trans_type == "Saída" and not t.is_paid)
            
            saldo_atual = acc.initial_balance + entradas - saidas_pagas
            saldo_total_geral += saldo_atual

            saldos_data.append({
                "Banco / Conta": acc.bank_name,
                "Saldo Inicial": acc.initial_balance,
                "Entradas (Pagas)": entradas,
                "Saídas (Pagas)": saidas_pagas,
                "Saídas Pendentes": saidas_pendentes,
                "Saldo Atual": saldo_atual
            })

        st.metric(label="💰 Saldo Total Consolidado", value=f"R$ {saldo_total_geral:,.2f}")
        st.markdown("---")

        st.dataframe(
            pd.DataFrame(saldos_data),
            column_config={
                "Saldo Inicial": st.column_config.NumberColumn(format="R$ %.2f"),
                "Entradas (Pagas)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Saídas (Pagas)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Saídas Pendentes": st.column_config.NumberColumn(format="R$ %.2f"),
                "Saldo Atual": st.column_config.NumberColumn(format="R$ %.2f")
            },
            hide_index=True,
            use_container_width=True
        )

# =========================================================
# ABA 4: FATURAS DE CARTÃO DE CRÉDITO
# =========================================================
with tab_faturas:
    st.markdown("### 💳 Faturas de Cartão de Crédito")
    
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    
    if not user_cards:
        st.info("Nenhum cartão de crédito cadastrado para este usuário.")
    else:
        col_c, col_m, col_a = st.columns(3)
        
        with col_c:
            card_dict = {c.card_name: c for c in user_cards}
            sel_card_name = st.selectbox("Selecione o Cartão:", list(card_dict.keys()))
            sel_card = card_dict[sel_card_name]

        with col_m:
            meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
            mes_sel = st.selectbox("Mês de Vencimento:", meses, index=datetime.date.today().month - 1)
            mes_venc_num = meses.index(mes_sel) + 1

        with col_a:
            ano_atual = datetime.date.today().year
            ano_venc_num = st.number_input("Ano de Vencimento:", min_value=2020, max_value=2035, value=ano_atual)

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
            if ref_date.day >= dia_fechamento:
                data_vencimento_fatura = ref_date + dateutil.relativedelta.relativedelta(months=1)
            else:
                data_vencimento_fatura = ref_date

            if data_vencimento_fatura.month == mes_venc_num and data_vencimento_fatura.year == ano_venc_num:
                fatura_items.append(t)

        total_fatura = sum(t.amount for t in fatura_items)

        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        m1.metric(f"Fatura Vencimento ({mes_sel}/{ano_venc_num})", f"R$ {total_fatura:,.2f}")
        m2.metric("Dia do Vencimento", f"Dia {sel_card.due_day}")
        m3.metric("Fechamento Aprox.", f"Dia {dia_fechamento}")

        with st.expander("💵 **Quitar / Pagar Fatura**"):
            if not user_accounts:
                st.warning("Cadastre uma Conta Corrente para registrar o pagamento da fatura.")
            elif total_fatura <= 0:
                st.info("Esta fatura não possui lançamentos pendentes a serem pagos.")
            else:
                with st.form("form_pagar_fatura", clear_on_submit=True):
                    acc_pay_dict = {a.bank_name: a.id for a in user_accounts}
                    sel_acc_pay_name = st.selectbox("Conta Corrente de Origem:", list(acc_pay_dict.keys()))
                    valor_pagamento = st.number_input("Valor a Pagar (R$):", value=float(total_fatura), min_value=0.01, step=10.0)
                    data_pagamento = st.date_input("Data do Pagamento:", value=st.session_state.ultima_data_lancamento)
                    metodo_pagamento = st.selectbox("Forma de Pagamento:", ["PIX", "Débito Automático", "Boleto / TED"])
                    
                    btn_pagar = st.form_submit_button("Confirmar Pagamento da Fatura")
                    
                    if btn_pagar:
                        acc_pay_id = acc_pay_dict[sel_acc_pay_name]
                        desc_pagto = f"Pagamento Fatura {sel_card.card_name} ({mes_sel}/{ano_venc_num})"
                        
                        for item in fatura_items:
                            item.is_paid = True
                        
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
                        st.success(f"Pagamento de R$ {valor_pagamento:.2f} efetuado e lançamentos quitados com sucesso!")
                        st.rerun()

        st.markdown(f"#### Lançamentos pendentes na Fatura de **{mes_sel}/{ano_venc_num}**")
        if fatura_items:
            df_fat = pd.DataFrame([{
                "Data Compra": t.purchase_date or t.date,
                "Data Parcela": t.date,
                "Descrição": t.description,
                "Categoria": t.category_name,
                "Método / Parcela": t.method,
                "Valor (R$)": t.amount
            } for t in fatura_items])

            st.dataframe(
                df_fat,
                column_config={
                    "Data Compra": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Data Parcela": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Valor (R$)": st.column_config.NumberColumn(format="R$ %.2f")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info(f"Nenhum lançamento pendente para a fatura de {mes_sel}/{ano_venc_num}.")

# =========================================================
# ABA 5: LANÇAMENTOS & EDIÇÃO
# =========================================================
with tab_lancamentos:
    st.markdown("### 📝 Registrar Novo Lançamento")
    
    user_accounts = db.query(BankAccount).filter(BankAccount.user_id == current_user.id).all()
    user_cards = db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()

    if not user_accounts and not user_cards:
        st.info("Cadastre uma Conta ou Cartão de Crédito para realizar lançamentos.")
    else:
        origem = st.radio("Origem do Lançamento:", ["Conta Corrente (PIX, TED, Saque)", "Cartão de Crédito"], horizontal=True)

        if origem == "Conta Corrente (PIX, TED, Saque)":
            if not user_accounts:
                st.warning("Você não possui contas correntes cadastradas.")
            else:
                acc_idx = min(st.session_state.ultima_conta_index, len(user_accounts) - 1)

                trans_type = st.selectbox("Tipo de Movimentação:", ["Saída", "Entrada"], key="acc_trans_type_sel")

                with st.form("form_trans_acc", clear_on_submit=True):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        acc_dict = {a.bank_name: (a.id, idx) for idx, a in enumerate(user_accounts)}
                        lista_contas = list(acc_dict.keys())
                        
                        sel_acc_label = st.selectbox("Selecione a Conta:", lista_contas, index=acc_idx)
                        sel_acc_id, sel_acc_idx = acc_dict[sel_acc_label]
                    
                    with col2:
                        cats = db.query(Category).filter(Category.type == trans_type).all()
                        sel_cat = st.selectbox("Classificação / Categoria:", [c.name for c in cats])
                        method = st.selectbox("Método:", ["PIX", "Boleto", "TED", "Saque", "Débito Automático", "Outro"])
                    
                    with col3:
                        amount = st.number_input("Valor Mensal / Individual (R$):", min_value=0.01, step=10.0)
                        trans_date = st.date_input("Data do Lançamento / Vencimento Inicial:", value=st.session_state.ultima_data_lancamento)
                        status_pago = st.checkbox("1ª Parcela/Lançamento já foi pago?", value=True)

                    desc = st.text_input("Descrição / Observação:", placeholder="Ex: Aluguel, Plano de Saúde, Salário")

                    st.markdown("---")
                    st.markdown("#### 🔄 Recorrência / Repetição")
                    col_rec1, col_rec2 = st.columns(2)
                    with col_rec1:
                        is_recurring = st.checkbox("Lançamento Recorrente (Repetir nos próximos meses)?")
                    with col_rec2:
                        qnt_meses = st.number_input("Prazo / Quantidade de Meses:", min_value=1, max_value=60, value=12, step=1, disabled=not is_recurring)

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
                                    purchase_date=data_futura,
                                    date=data_futura,
                                    trans_type=trans_type,
                                    method=method,
                                    is_paid=pago_futuro
                                )
                                db.add(new_t)
                            
                            db.commit()
                            
                            st.session_state.ultima_data_lancamento = trans_date
                            st.session_state.ultima_conta_index = sel_acc_idx
                            
                            if is_recurring:
                                st.success(f"Recorrência de {total_repeticoes} meses cadastrada com sucesso!")
                            else:
                                st.success("Lançamento em conta corrente salvo com sucesso!")
                            st.rerun()
                        else:
                            st.error("Preencha a descrição do lançamento.")

        else: # Cartão de Crédito
            if not user_cards:
                st.warning("Você não possui cartões de crédito cadastrados.")
            else:
                card_idx = min(st.session_state.ultimo_cartao_index, len(user_cards) - 1)

                with st.form("form_trans_card", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        card_dict = {f"{c.card_name} (Venc: Dia {c.due_day})": (c, idx) for idx, c in enumerate(user_cards)}
                        lista_cartoes = list(card_dict.keys())
                        
                        sel_card_label = st.selectbox("Selecione o Cartão:", lista_cartoes, index=card_idx)
                        sel_card_obj, sel_card_idx = card_dict[sel_card_label]
                        
                        cats = db.query(Category).filter(Category.type == "Saída").all()
                        sel_cat = st.selectbox("Classificação / Categoria:", [c.name for c in cats])
                        total_amount = st.number_input("Valor Total da Compra (R$):", min_value=0.01, step=10.0)
                    
                    with col2:
                        parcelas = st.number_input("Número de Parcelas:", min_value=1, max_value=48, value=1, step=1)
                        purchase_date_input = st.date_input("Data da Compra:", value=st.session_state.ultima_data_lancamento)
                        
                        valor_parcela = total_amount / parcelas if parcelas > 0 else total_amount
                        st.info(f"💡 **{parcelas}x** de **R$ {valor_parcela:.2f}** (cadastrado como **🟡 Pendente**)")

                    desc = st.text_input("Descrição / Observação:", placeholder="Ex: Compra de supermercado")
                    btn_save_card_trans = st.form_submit_button("💾 Salvar Lançamento no Cartão")

                    if btn_save_card_trans:
                        if desc:
                            valor_parcela = total_amount / parcelas

                            for i in range(parcelas):
                                data_parcela = purchase_date_input + dateutil.relativedelta.relativedelta(months=i)
                                desc_parcelada = f"{desc} ({i+1}/{parcelas})" if parcelas > 1 else desc
                                metodo_str = f"Cartão ({parcelas}x)" if parcelas > 1 else "Cartão (À vista)"

                                new_t = Transaction(
                                    user_id=current_user.id,
                                    card_id=sel_card_obj.id,
                                    category_name=sel_cat,
                                    description=desc_parcelada,
                                    amount=valor_parcela,
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
                            
                            st.success(f"Compra parcelada registrada como PENDENTE! Todas as {parcelas} parcelas foram geradas.")
                            st.rerun()
                        else:
                            st.error("Preencha a descrição.")

    st.markdown("---")
    st.markdown("### 📋 Histórico & Edição de Lançamentos")

    user_trans_query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    all_trans = user_trans_query.order_by(Transaction.date.desc()).all()

    if all_trans:
        with st.expander("🔍 **Filtros de Busca**", expanded=True):
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            
            with f_col1:
                tipo_filter = st.selectbox("Filtrar Tipo:", ["Todos", "Entrada", "Saída"])
            with f_col2:
                status_filter = st.selectbox("Filtrar Status:", ["Todos", "Apenas Pagos", "Apenas Pendentes / Não Pagos"])
            
            opcoes_cartoes = ["Todos"] + [c.card_name for c in user_cards]
            with f_col3:
                cartao_filter = st.selectbox("Filtrar por Cartão:", opcoes_cartoes)
                
            with f_col4:
                busca_desc = st.text_input("Buscar por Descrição:", placeholder="Ex: Aluguel")

        filtered_trans = all_trans
        if tipo_filter != "Todos":
            filtered_trans = [t for t in filtered_trans if t.trans_type == tipo_filter]
            
        if status_filter == "Apenas Pagos":
            filtered_trans = [t for t in filtered_trans if t.is_paid]
        elif status_filter == "Apenas Pendentes / Não Pagos":
            filtered_trans = [t for t in filtered_trans if not t.is_paid]
            
        if cartao_filter != "Todos":
            filtered_trans = [t for t in filtered_trans if t.card and t.card.card_name == cartao_filter]
            
        if busca_desc:
            filtered_trans = [t for t in filtered_trans if busca_desc.lower() in t.description.lower()]

        if filtered_trans:
            all_cat_names = [c.name for c in db.query(Category).all()]
            
            data_table = []
            for t in filtered_trans:
                origem_nome = f"🏦 {t.account.bank_name}" if t.account else f"💳 {t.card.card_name}"
                status_str = "🟢 Pago" if t.is_paid else "🟡 Pendente"
                data_table.append({
                    "ID": t.id,
                    "Data Compra": t.purchase_date or t.date,
                    "Data Parcela": t.date,
                    "Status": status_str,
                    "Tipo": t.trans_type,
                    "Origem": origem_nome,
                    "Categoria": t.category_name,
                    "Descrição": t.description,
                    "Valor (R$)": float(t.amount)
                })

            st.markdown("""
                <style>
                div[data-testid="stTable"] { font-size: 14px; }
                </style>
            """, unsafe_allow_html=True)

            edited_df = st.data_editor(
                pd.DataFrame(data_table),
                column_config={
                    "ID": st.column_config.NumberColumn("ID", disabled=True),
                    "Data Compra": st.column_config.DateColumn("Data Compra", format="DD/MM/YYYY"),
                    "Data Parcela": st.column_config.DateColumn("Data Parcela", format="DD/MM/YYYY"),
                    "Status": st.column_config.SelectboxColumn("Status", options=["🟢 Pago", "🟡 Pendente"]),
                    "Tipo": st.column_config.TextColumn("Tipo", disabled=True),
                    "Origem": st.column_config.TextColumn("Origem", disabled=True),
                    "Categoria": st.column_config.SelectboxColumn("Categoria", options=all_cat_names),
                    "Descrição": st.column_config.TextColumn("Descrição"),
                    "Valor (R$)": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f", min_value=0.01)
                },
                hide_index=True,
                use_container_width=True,
                key="editor_lancamentos"
            )

            col_save, _ = st.columns([2, 3])
            with col_save:
                if st.button("💾 Salvar Alterações da Tabela"):
                    for _, row in edited_df.iterrows():
                        trans_db = db.query(Transaction).filter(Transaction.id == int(row["ID"])).first()
                        if trans_db:
                            trans_db.purchase_date = row["Data Compra"]
                            trans_db.date = row["Data Parcela"]
                            trans_db.is_paid = True if "Pago" in str(row["Status"]) else False
                            trans_db.category_name = row["Categoria"]
                            trans_db.description = str(row["Descrição"])
                            trans_db.amount = float(row["Valor (R$)"])
                    db.commit()
                    st.success("Lançamentos atualizados!")
                    st.rerun()

            st.markdown("---")
            with st.expander("🗑️ **Excluir um Lançamento**"):
                trans_dict = {f"ID #{t.id} - {t.description} (R$ {t.amount:.2f} em {t.date.strftime('%d/%m/%Y')})": t for t in filtered_trans}
                selected_trans_label = st.selectbox("Selecione o lançamento para excluir:", list(trans_dict.keys()))
                selected_trans = trans_dict[selected_trans_label]

                if st.button(f"Confirmar Exclusão do Lançamento #{selected_trans.id}"):
                    db.delete(selected_trans)
                    db.commit()
                    st.success("Lançamento excluído!")
                    st.rerun()
        else:
            st.warning("Nenhum lançamento encontrado para os filtros selecionados.")
    else:
        st.info("Nenhum lançamento registrado ainda.")

db.close()