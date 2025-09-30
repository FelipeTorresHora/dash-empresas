# 🏢 Dashboard de Empresas

Dashboard interativo para consulta e análise de dados de empresas brasileiras, construído com Streamlit e PostgreSQL.

## 📋 Funcionalidades

- **Busca Inteligente**: Consulta por razão social com suporte a buscas parciais
- **Filtros Avançados**:
  - Porte da empresa
  - Natureza jurídica
  - Qualificação do responsável
  - Faixa de capital social
- **Paginação Otimizada**: Navegação eficiente com limite de 10.000 registros
- **Performance**: Cache de metadados e queries otimizadas
- **Rate Limiting**: Controle de requisições para proteger o banco
- **Download de Dados**: Exportação dos resultados em CSV
- **Métricas em Tempo Real**: Tempo de consulta e contadores

## 🛠 Tecnologias

- **Python 3.8+**
- **Streamlit** - Framework web para dashboards
- **PostgreSQL** - Banco de dados
- **pandas** - Manipulação de dados
- **SQLAlchemy** - ORM e conexão com banco
- **psycopg2** - Driver PostgreSQL

## 📦 Requisitos

- Python 3.8 ou superior
- PostgreSQL 12 ou superior
- Conexão com banco de dados contendo tabela `empresas`

## 🚀 Instalação

1. **Clone ou baixe o projeto**:
```bash
cd DB_RFB
```

2. **Crie um ambiente virtual**:
```bash
python -m venv venv
```

3. **Ative o ambiente virtual**:

Windows:
```bash
venv\Scripts\activate
```

Linux/Mac:
```bash
source venv/bin/activate
```

4. **Instale as dependências**:
```bash
pip install -r requirements.txt
```

## ⚙️ Configuração

Crie o arquivo `.streamlit/secrets.toml` com as credenciais do banco de dados:

```toml
[postgres]
host = "seu-host.com"
port = "5432"
dbname = "nome_do_banco"
user = "usuario"
password = "senha"
```

**Importante**: Nunca compartilhe ou versione este arquivo com credenciais reais.

## 🎮 Como Usar

1. **Inicie o aplicativo**:
```bash
streamlit run app.py
```

2. **Acesse no navegador**: O Streamlit abrirá automaticamente em `http://localhost:8501`

3. **Use os filtros**:
   - Digite uma razão social na barra lateral
   - Clique em "Carregar Filtros Avançados" para mais opções
   - Configure porte, natureza jurídica, qualificação e capital social
   - Clique em "Aplicar Filtros"

4. **Navegue pelos resultados**:
   - Use os botões de paginação
   - Baixe os resultados em CSV (limitado a 1000 registros)

## 🗂 Estrutura do Projeto

```
DB_RFB/
├── app.py              # Aplicação principal
├── requirements.txt    # Dependências Python
├── .streamlit/
│   └── secrets.toml   # Credenciais do banco (não versionado)
├── venv/              # Ambiente virtual (não versionado)
└── README.md          # Este arquivo
```

## 📊 Estrutura da Tabela

O aplicativo detecta automaticamente a estrutura da tabela `empresas` e mapeia as seguintes colunas (aceita variações de nomes):

- **CNPJ**: `cnpj_basico`, `cnpj`, `cnpj_base`
- **Razão Social**: `razao_social`, `nome_empresarial`, `nome`
- **Natureza Jurídica**: `natureza_juridica`, `natureza`
- **Qualificação**: `qualificacao_responsavel`, `qualificacao`
- **Capital Social**: `capital_social`, `capital`
- **Porte**: `porte`, `porte_empresa`, `cod_porte`

## 🚀 Otimizações Recomendadas

Para melhorar a performance do banco de dados, execute os seguintes comandos SQL:

```sql
-- Criar índices para acelerar consultas
CREATE INDEX CONCURRENTLY idx_razao_social ON empresas(razao_social);
CREATE INDEX CONCURRENTLY idx_porte ON empresas(porte);
CREATE INDEX CONCURRENTLY idx_natureza ON empresas(natureza_juridica);
CREATE INDEX CONCURRENTLY idx_qualificacao ON empresas(qualificacao_responsavel);
CREATE INDEX CONCURRENTLY idx_capital ON empresas(capital_social);

-- Habilitar busca fuzzy (opcional)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX CONCURRENTLY idx_razao_trgm ON empresas USING gin (razao_social gin_trgm_ops);

-- Atualizar estatísticas do banco
ANALYZE empresas;
```

## ⚡ Features Técnicas

- **Cache Inteligente**: Metadados em cache por 24 horas
- **Pool de Conexões**: SQLAlchemy com pool otimizado
- **Rate Limiting**: Cooldown de 2 segundos entre buscas
- **Limites de Segurança**:
  - Máximo de 10.000 registros navegáveis
  - Máximo de 500 páginas
  - Download limitado a 1.000 registros
- **Estimativas Rápidas**: Usa estatísticas do PostgreSQL para contagens

## 🔧 Configurações Ajustáveis

No arquivo `app.py`, você pode ajustar:

```python
TOTAL_EMPRESAS_APROXIMADO = 5_000_000  # Total estimado
MAX_OFFSET = 10000                      # Máximo de registros navegáveis
MAX_PAGINAS = 500                       # Máximo de páginas
COOLDOWN_SECONDS = 2                    # Tempo entre buscas
```

## 📝 Notas

- O dashboard foi otimizado para grandes volumes de dados (milhões de registros)
- Filtros são aplicados diretamente no banco para máxima eficiência
- A primeira carga é mais lenta devido ao carregamento de metadados
- Use filtros específicos para melhores resultados

## 🐛 Troubleshooting

**Erro de conexão com banco**:
- Verifique as credenciais em `.streamlit/secrets.toml`
- Confirme que o PostgreSQL está rodando
- Teste a conexão com `psql` ou outro cliente

**Consultas lentas**:
- Aplique os índices recomendados
- Use filtros mais específicos
- Verifique o plano de execução com `EXPLAIN`

**Erro ao mapear colunas**:
- Acesse "Informações da Tabela" para ver estrutura real
- Ajuste o mapeamento em `get_column_mapping()` se necessário

## 📄 Licença

Este projeto é de uso interno. Ajuste conforme necessário para sua organização.
