import streamlit as st
import psycopg2
import pandas as pd
from sqlalchemy import create_engine
import time

# Define o título da página e um ícone
st.set_page_config(
    page_title="Dashboard Empresas",
    page_icon="🏢",
    layout="wide"
)

# -------------------------------------------------------------------
# CONFIGURAÇÕES GLOBAIS
# -------------------------------------------------------------------

# Total aproximado de empresas (atualizar manualmente quando necessário)
TOTAL_EMPRESAS_APROXIMADO = 5_000_000

# Limites de segurança
MAX_OFFSET = 10000  # Máximo de registros navegáveis
MAX_PAGINAS = 500   # Máximo de páginas
COOLDOWN_SECONDS = 2  # Tempo mínimo entre buscas

# -------------------------------------------------------------------
# FUNÇÕES DE CONEXÃO E CONSULTA AO BANCO DE DADOS
# -------------------------------------------------------------------

@st.cache_resource
def get_engine():
    """
    Cria um engine de conexão do SQLAlchemy usando as credenciais do Streamlit secrets.
    """
    try:
        db_url = (
            f"postgresql+psycopg2://{st.secrets['postgres']['user']}:{st.secrets['postgres']['password']}"
            f"@{st.secrets['postgres']['host']}:{st.secrets['postgres']['port']}"
            f"/{st.secrets['postgres']['dbname']}"
        )
        engine = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        return engine
    except Exception as e:
        st.error(f"Erro ao criar a conexão com o banco de dados: {e}")
        return None

def run_query(query, params=None):
    """
    Executa uma query no banco de dados usando o engine do SQLAlchemy
    e retorna o resultado como um DataFrame.
    """
    engine = get_engine()
    if engine is not None:
        try:
            start_time = time.time()
            with engine.connect() as connection:
                df = pd.read_sql_query(query, connection, params=params)
                end_time = time.time()
                query_time = round(end_time - start_time, 2)
                return df, query_time
        except Exception as e:
            st.error(f"Erro ao executar a query: {e}")
            return pd.DataFrame(), 0
    return pd.DataFrame(), 0

# -------------------------------------------------------------------
# VERIFICAÇÃO DA ESTRUTURA DA TABELA
# -------------------------------------------------------------------

@st.cache_data(ttl=86400)  # Cache 24 horas
def get_table_structure():
    """
    Verifica a estrutura real da tabela empresas.
    """
    query = """
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'empresas'
    ORDER BY ordinal_position;
    """
    df, _ = run_query(query)
    return df

@st.cache_data(ttl=86400)
def get_column_mapping():
    """
    Mapeia as colunas reais da tabela para nomes padrão.
    """
    df_estrutura = get_table_structure()
    if df_estrutura.empty:
        return None
    
    colunas_disponiveis = df_estrutura['column_name'].str.lower().tolist()
    
    mapeamento_colunas = {}
    colunas_necessarias = {
        'cnpj': ['cnpj_basico', 'cnpj', 'cnpj_base', 'numero_cnpj'],
        'razao_social': ['razao_social', 'nome_empresarial', 'nome', 'razao'],
        'natureza_juridica': ['natureza_juridica', 'natureza', 'nat_juridica'],
        'qualificacao': ['qualificacao_responsavel', 'qualificacao', 'qual_responsavel'],
        'capital_social': ['capital_social', 'capital', 'valor_capital'],
        'porte': ['porte', 'porte_empresa', 'cod_porte']
    }
    
    for campo, opcoes in colunas_necessarias.items():
        for opcao in opcoes:
            if opcao.lower() in colunas_disponiveis:
                nome_real = df_estrutura[df_estrutura['column_name'].str.lower() == opcao.lower()]['column_name'].iloc[0]
                mapeamento_colunas[campo] = nome_real
                break
    
    return mapeamento_colunas if len(mapeamento_colunas) == 6 else None

# -------------------------------------------------------------------
# FUNÇÕES DE METADADOS (CACHE LONGO E OTIMIZADO)
# -------------------------------------------------------------------

@st.cache_data(ttl=86400)  # Cache 24 horas
def get_total_records_estimate():
    """
    Obtém estimativa rápida do total de registros usando estatísticas do PostgreSQL.
    """
    query = """
    SELECT reltuples::bigint AS estimate
    FROM pg_class
    WHERE relname = 'empresas';
    """
    df, _ = run_query(query)
    if not df.empty and df['estimate'].iloc[0] > 0:
        return int(df['estimate'].iloc[0])
    return TOTAL_EMPRESAS_APROXIMADO

@st.cache_data(ttl=86400)  # Cache 24 horas
def get_metadata(mapeamento_colunas):
    """
    Obtém metadados da tabela para popular os filtros de forma otimizada.
    """
    queries = {
        'portes': f"""
            SELECT DISTINCT {mapeamento_colunas['porte']} as porte 
            FROM empresas 
            WHERE {mapeamento_colunas['porte']} IS NOT NULL 
            ORDER BY {mapeamento_colunas['porte']}
            LIMIT 10
        """,
        'natureza_juridica': f"""
            SELECT DISTINCT {mapeamento_colunas['natureza_juridica']} as natureza_juridica
            FROM empresas 
            WHERE {mapeamento_colunas['natureza_juridica']} IS NOT NULL 
            ORDER BY {mapeamento_colunas['natureza_juridica']}
            LIMIT 50
        """,
        'qualificacao': f"""
            SELECT DISTINCT {mapeamento_colunas['qualificacao']} as qualificacao_responsavel
            FROM empresas 
            WHERE {mapeamento_colunas['qualificacao']} IS NOT NULL 
            ORDER BY {mapeamento_colunas['qualificacao']}
            LIMIT 50
        """
    }
    
    metadata = {}
    for key, query in queries.items():
        df, _ = run_query(query)
        metadata[key] = df
    
    return metadata

# -------------------------------------------------------------------
# FUNÇÃO PRINCIPAL DE BUSCA
# -------------------------------------------------------------------

def build_query(busca_nome, portes_selecionados, natureza_selecionada, 
                qualificacao_selecionada, capital_min, capital_max, 
                limit, offset, mapeamento_colunas):
    """
    Constrói a query SQL baseada nos filtros selecionados.
    """
    # Limitar offset máximo
    if offset > MAX_OFFSET:
        offset = MAX_OFFSET
    
    # Query base com nomes reais das colunas
    query = f"""
    SELECT {mapeamento_colunas['cnpj']} as cnpj_basico, 
           {mapeamento_colunas['razao_social']} as razao_social, 
           {mapeamento_colunas['natureza_juridica']} as natureza_juridica,
           {mapeamento_colunas['qualificacao']} as qualificacao_responsavel, 
           {mapeamento_colunas['capital_social']} as capital_social, 
           {mapeamento_colunas['porte']} as porte
    FROM empresas
    WHERE 1=1
    """
    
    params = {}
    
    # Filtro por nome/razão social
    if busca_nome:
        query += f" AND UPPER({mapeamento_colunas['razao_social']}) LIKE UPPER(%(busca_nome)s)"
        params['busca_nome'] = f"%{busca_nome}%"
    
    # Filtro por porte
    if portes_selecionados:
        placeholders = ','.join([f"%(porte_{i})s" for i in range(len(portes_selecionados))])
        query += f" AND {mapeamento_colunas['porte']} IN ({placeholders})"
        for i, porte in enumerate(portes_selecionados):
            params[f'porte_{i}'] = porte
    
    # Filtro por natureza jurídica
    if natureza_selecionada and natureza_selecionada != 'Todas':
        query += f" AND {mapeamento_colunas['natureza_juridica']} = %(natureza)s"
        params['natureza'] = natureza_selecionada
    
    # Filtro por qualificação
    if qualificacao_selecionada and qualificacao_selecionada != 'Todas':
        query += f" AND {mapeamento_colunas['qualificacao']} = %(qualificacao)s"
        params['qualificacao'] = qualificacao_selecionada
    
    # Filtro por capital social
    if capital_min is not None:
        query += f" AND {mapeamento_colunas['capital_social']} >= %(capital_min)s"
        params['capital_min'] = capital_min
    
    if capital_max is not None:
        query += f" AND {mapeamento_colunas['capital_social']} <= %(capital_max)s"
        params['capital_max'] = capital_max
    
    # Ordenação e paginação
    query += f" ORDER BY {mapeamento_colunas['razao_social']}"
    query += f" LIMIT {limit} OFFSET {offset}"
    
    return query, params

def get_filtered_count(busca_nome, portes_selecionados, natureza_selecionada, 
                      qualificacao_selecionada, capital_min, capital_max, mapeamento_colunas):
    """
    Obtém o total de registros que atendem aos filtros.
    Usa EXPLAIN para estimativa rápida quando possível.
    """
    query = "SELECT COUNT(*) as total FROM empresas WHERE 1=1"
    params = {}
    
    if busca_nome:
        query += f" AND UPPER({mapeamento_colunas['razao_social']}) LIKE UPPER(%(busca_nome)s)"
        params['busca_nome'] = f"%{busca_nome}%"
    
    if portes_selecionados:
        placeholders = ','.join([f"%(porte_{i})s" for i in range(len(portes_selecionados))])
        query += f" AND {mapeamento_colunas['porte']} IN ({placeholders})"
        for i, porte in enumerate(portes_selecionados):
            params[f'porte_{i}'] = porte
    
    if natureza_selecionada and natureza_selecionada != 'Todas':
        query += f" AND {mapeamento_colunas['natureza_juridica']} = %(natureza)s"
        params['natureza'] = natureza_selecionada
    
    if qualificacao_selecionada and qualificacao_selecionada != 'Todas':
        query += f" AND {mapeamento_colunas['qualificacao']} = %(qualificacao)s"
        params['qualificacao'] = qualificacao_selecionada
    
    if capital_min is not None:
        query += f" AND {mapeamento_colunas['capital_social']} >= %(capital_min)s"
        params['capital_min'] = capital_min
    
    if capital_max is not None:
        query += f" AND {mapeamento_colunas['capital_social']} <= %(capital_max)s"
        params['capital_max'] = capital_max
    
    df, _ = run_query(query, params)
    return df['total'].iloc[0] if not df.empty else 0

def is_heavy_query(busca_nome, portes, natureza, qualificacao, capital_min, capital_max):
    """
    Detecta se query pode ser pesada e demorada.
    """
    # Se tem busca por nome ou filtros específicos, não é pesado
    if busca_nome or capital_min or capital_max:
        return False
    
    # Se tem filtros específicos de natureza ou qualificação
    if natureza != 'Todas' or qualificacao != 'Todas':
        return False
    
    # Se tem poucos portes selecionados
    if portes and len(portes) <= 2:
        return False
    
    # Caso contrário, pode ser pesado
    return True

# -------------------------------------------------------------------
# INTERFACE PRINCIPAL
# -------------------------------------------------------------------

st.title("🏢 Dashboard de Empresas")
st.markdown("Busca otimizada com filtros dinâmicos aplicados diretamente no banco de dados.")

# Verificar estrutura da tabela e mapeamento
mapeamento_colunas = get_column_mapping()

if mapeamento_colunas is None:
    st.error("❌ Não foi possível mapear as colunas da tabela. Verifique a conexão com o banco de dados.")
    
    with st.expander("🔍 Estrutura da Tabela", expanded=True):
        df_estrutura = get_table_structure()
        if not df_estrutura.empty:
            st.write("**Colunas disponíveis na tabela:**")
            st.dataframe(df_estrutura)
        else:
            st.error("Não foi possível verificar a estrutura da tabela")
    st.stop()

# Mostrar informações de mapeamento (opcional)
with st.expander("ℹ️ Informações da Tabela", expanded=False):
    st.success(f"✅ Colunas mapeadas com sucesso!")
    st.json(mapeamento_colunas)
    
    df_estrutura = get_table_structure()
    if not df_estrutura.empty:
        st.write("**Estrutura completa:**")
        st.dataframe(df_estrutura, use_container_width=True)

# Sidebar com filtros
st.sidebar.header("🔍 Filtros de Busca")

# Inicializar session state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'last_search_time' not in st.session_state:
    st.session_state.last_search_time = None
if 'filtros_carregados' not in st.session_state:
    st.session_state.filtros_carregados = False

# Filtro de busca por nome (sempre visível)
busca_nome = st.sidebar.text_input(
    "Buscar por Razão Social:",
    placeholder="Digite parte do nome da empresa..."
)

# Botão para carregar filtros avançados
if not st.session_state.filtros_carregados:
    if st.sidebar.button("📋 Carregar Filtros Avançados"):
        st.session_state.filtros_carregados = True
        st.rerun()
    
    # Valores padrão quando filtros não carregados
    portes_selecionados = []
    natureza_selecionada = 'Todas'
    qualificacao_selecionada = 'Todas'
    capital_min = None
    capital_max = None
    
else:
    # Carrega metadados apenas se necessário
    with st.spinner("Carregando opções de filtros..."):
        metadata = get_metadata(mapeamento_colunas)
    
    # Filtro por porte
    portes_disponiveis = []
    if not metadata['portes'].empty:
        portes_disponiveis = metadata['portes']['porte'].tolist()
    
    portes_selecionados = st.sidebar.multiselect(
        "Porte da Empresa:",
        options=portes_disponiveis,
        default=[]
    )
    
    # Filtro por natureza jurídica
    natureza_options = ['Todas']
    if not metadata['natureza_juridica'].empty:
        natureza_options.extend(metadata['natureza_juridica']['natureza_juridica'].tolist())
    
    natureza_selecionada = st.sidebar.selectbox(
        "Natureza Jurídica:",
        options=natureza_options,
        index=0
    )
    
    # Filtro por qualificação do responsável
    qualificacao_options = ['Todas']
    if not metadata['qualificacao'].empty:
        qualificacao_options.extend(metadata['qualificacao']['qualificacao_responsavel'].tolist())
    
    qualificacao_selecionada = st.sidebar.selectbox(
        "Qualificação do Responsável:",
        options=qualificacao_options,
        index=0
    )
    
    # Filtro por capital social
    st.sidebar.subheader("Capital Social (R$)")
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        capital_min = st.number_input(
            "Mínimo:",
            min_value=0.0,
            value=None,
            step=1000.0,
            format="%.2f"
        )
    
    with col2:
        capital_max = st.number_input(
            "Máximo:",
            min_value=0.0,
            value=None,
            step=1000.0,
            format="%.2f"
        )

# Controles de paginação
st.sidebar.subheader("⚙️ Controles")
registros_por_pagina = st.sidebar.selectbox(
    "Registros por página:",
    options=[20, 50, 100],
    index=0
)

# Rate limiting
pode_buscar = True
if st.session_state.last_search_time:
    from datetime import datetime, timedelta
    tempo_passado = (datetime.now() - st.session_state.last_search_time).total_seconds()
    if tempo_passado < COOLDOWN_SECONDS:
        st.sidebar.warning(f"⏳ Aguarde {COOLDOWN_SECONDS - int(tempo_passado)}s para nova busca")
        pode_buscar = False

# Botão de aplicar filtros
aplicar_filtros = st.sidebar.button("🔍 Aplicar Filtros", type="primary", disabled=not pode_buscar)

# Aviso de query pesada
if aplicar_filtros and is_heavy_query(busca_nome, portes_selecionados, natureza_selecionada, 
                                       qualificacao_selecionada, capital_min, capital_max):
    st.warning("⚠️ Esta busca sem filtros específicos pode demorar. Considere adicionar filtros de nome ou capital.")

# Reset página ao aplicar novos filtros
if aplicar_filtros:
    st.session_state.current_page = 1
    from datetime import datetime
    st.session_state.last_search_time = datetime.now()

# -------------------------------------------------------------------
# ÁREA PRINCIPAL COM RESULTADOS
# -------------------------------------------------------------------

# Calcular offset para paginação
offset = (st.session_state.current_page - 1) * registros_por_pagina

# Limitar offset máximo
if offset > MAX_OFFSET:
    st.warning(f"⚠️ Navegação limitada aos primeiros {MAX_OFFSET:,} registros. Use filtros mais específicos.")
    offset = MAX_OFFSET

# Construir e executar query
query, params = build_query(
    busca_nome, portes_selecionados, natureza_selecionada,
    qualificacao_selecionada, capital_min, capital_max,
    registros_por_pagina, offset, mapeamento_colunas
)

# Executar busca
with st.spinner("Executando busca no banco de dados..."):
    df_resultados, query_time = run_query(query, params)
    
    # Calcular total filtrado apenas quando necessário (não na primeira carga)
    if aplicar_filtros or st.session_state.current_page > 1:
        with st.spinner("Contando resultados..."):
            total_filtrado = get_filtered_count(
                busca_nome, portes_selecionados, natureza_selecionada,
                qualificacao_selecionada, capital_min, capital_max, mapeamento_colunas
            )
    else:
        # Estimativa baseada nos resultados
        if len(df_resultados) < registros_por_pagina:
            total_filtrado = offset + len(df_resultados)
        else:
            total_filtrado = None  # Desconhecido

# Obter estimativa do total (rápido)
total_registros = get_total_records_estimate()

# Métricas principais
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total de Empresas", 
        f"~{total_registros:,}".replace(",", ".")
    )

with col2:
    if total_filtrado is not None:
        st.metric(
            "Resultados Filtrados", 
            f"{total_filtrado:,}".replace(",", ".")
        )
    else:
        st.metric(
            "Resultados Filtrados", 
            f">{offset + registros_por_pagina:,}".replace(",", ".")
        )

with col3:
    st.metric(
        "Mostrando", 
        f"{len(df_resultados)} registros"
    )

with col4:
    st.metric(
        "Tempo de Consulta", 
        f"{query_time}s"
    )

# Resultados
if not df_resultados.empty:
    st.subheader("📊 Resultados da Busca")
    
    # Formatar capital social para exibição
    if 'capital_social' in df_resultados.columns:
        df_display = df_resultados.copy()
        df_display['capital_social'] = df_display['capital_social'].apply(
            lambda x: f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") 
            if pd.notnull(x) else "N/A"
        )
    else:
        df_display = df_resultados
    
    # Exibir tabela
    st.dataframe(df_display, use_container_width=True)
    
    # Controles de paginação
    if total_filtrado and total_filtrado > registros_por_pagina:
        st.subheader("📄 Navegação")
        
        total_paginas = min((total_filtrado - 1) // registros_por_pagina + 1, MAX_PAGINAS)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("⏮️ Primeira", disabled=(st.session_state.current_page == 1)):
                st.session_state.current_page = 1
                st.rerun()
        
        with col2:
            if st.button("◀️ Anterior", disabled=(st.session_state.current_page == 1)):
                st.session_state.current_page -= 1
                st.rerun()
        
        with col3:
            st.write(f"Página {st.session_state.current_page} de {total_paginas}")
        
        with col4:
            if st.button("▶️ Próxima", disabled=(st.session_state.current_page >= total_paginas)):
                st.session_state.current_page += 1
                st.rerun()
        
        with col5:
            if st.button("⏭️ Última", disabled=(st.session_state.current_page >= total_paginas)):
                st.session_state.current_page = total_paginas
                st.rerun()
        
        if total_paginas >= MAX_PAGINAS:
            st.info(f"ℹ️ Navegação limitada a {MAX_PAGINAS} páginas. Use filtros para refinar a busca.")
    
    # Botão de download
    if len(df_resultados) <= 1000:  # Limita download
        csv = df_resultados.to_csv(index=False)
        st.download_button(
            label="📥 Baixar Resultados (CSV)",
            data=csv,
            file_name=f"empresas_filtradas_{int(time.time())}.csv",
            mime="text/csv"
        )
    else:
        st.warning("⚠️ Muitos resultados para download. Use filtros mais específicos para baixar os dados.")

else:
    st.warning("🔍 Nenhum resultado encontrado com os filtros aplicados. Tente ajustar os critérios de busca.")

# Informações sobre a consulta (para debug)
with st.expander("ℹ️ Informações da Consulta (Debug)"):
    st.code(query, language="sql")
    st.write("**Parâmetros:**", params)
    st.write("**Tempo de execução:**", f"{query_time} segundos")
    
    # Dicas de otimização
    st.subheader("💡 Dicas de Otimização")
    st.markdown("""
    **Para melhorar ainda mais a performance, execute no PostgreSQL:**
    
    ```sql
    -- 1. Criar índices básicos
    CREATE INDEX CONCURRENTLY idx_razao_social ON empresas(razao_social);
    CREATE INDEX CONCURRENTLY idx_porte ON empresas(porte);
    CREATE INDEX CONCURRENTLY idx_natureza ON empresas(natureza_juridica);
    CREATE INDEX CONCURRENTLY idx_qualificacao ON empresas(qualificacao_responsavel);
    CREATE INDEX CONCURRENTLY idx_capital ON empresas(capital_social);
    
    -- 2. Habilitar busca fuzzy (opcional)
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    CREATE INDEX CONCURRENTLY idx_razao_trgm ON empresas USING gin (razao_social gin_trgm_ops);
    
    -- 3. Atualizar estatísticas
    ANALYZE empresas;
    ```
    """)