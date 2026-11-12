
from pathlib import Path
import psycopg2
import pandas as pd
from dotenv import load_dotenv

POSTGRES_DB = load_dotenv("POSTGRES_DB")
POSTGRES_USER = load_dotenv("POSTGRES_USER")
POSTGRES_PASSWORD = load_dotenv("POSTGRES_PASSWORD")
POSTGRES_PORT = load_dotenv("POSTGRES_PORT")

# Caminho dos microdados do Censo Escolar 2025
PASTA_DADOS = Path(
    "/home/juannicolas/Downloads/"
    "microdados_censo_escolar_2025_/"
    "microdados_censo_escolar_2025_v2/dados"
)

ARQUIVO_CSV = PASTA_DADOS / "Tabela_Matricula_2025_V2.csv"

# Banco SQLite criado dentro deste projeto
ARQUIVO_BANCO = Path(__file__).parent / "censo_escolar.db"

# Estados do Nordeste e Sudeste
UFS_PERMITIDAS = [
    "MA", "PI", "CE", "RN", "PB", "PE", "AL", "SE", "BA",
    "MG", "ES", "RJ", "SP"
]

# Campos solicitados na atividade
COLUNAS = [
    "NO_ENTIDADE",
    "CO_ENTIDADE",
    "NO_UF",
    "SG_UF",
    "CO_UF",
    "NO_MUNICIPIO",
    "CO_MUNICIPIO",
    "NU_ANO_CENSO",
    "QT_MAT_BAS",
    "QT_MAT_INF",
    "QT_MAT_FUND",
    "QT_MAT_MED",
    "QT_MAT_PROF",
    "QT_MAT_EJA",
    "QT_MAT_ESP",
]

# Correspondência entre CSV e SQLite
MAPEAMENTO = {
    "NO_ENTIDADE": "no_entidade",
    "CO_ENTIDADE": "co_entidade",
    "NO_UF": "no_uf",
    "SG_UF": "sg_uf",
    "CO_UF": "co_uf",
    "NO_MUNICIPIO": "no_municipio",
    "CO_MUNICIPIO": "co_municipio",
    "NU_ANO_CENSO": "nu_ano_censo",
    "QT_MAT_BAS": "qt_mat_bas",
    "QT_MAT_INF": "qt_mat_inf",
    "QT_MAT_FUND": "qt_mat_fund",
    "QT_MAT_MED": "qt_mat_med",
    "QT_MAT_PROF": "qt_mat_prof",
    "QT_MAT_EJA": "qt_mat_eja",
    "QT_MAT_ESP": "qt_mat_esp",
}


# CRIAÇÃO DA TABELA

def criar_tabela(conexao):
    """Cria a tabela para armazenar as instituições."""

    conexao.execute("DROP TABLE IF EXISTS instituicoesensino")

    conexao.execute("""
        CREATE TABLE instituicoesensino (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            no_entidade TEXT NOT NULL,
            co_entidade INTEGER NOT NULL UNIQUE,
            no_uf TEXT NOT NULL,
            sg_uf TEXT NOT NULL,
            co_uf INTEGER NOT NULL,
            no_municipio TEXT NOT NULL,
            co_municipio INTEGER NOT NULL,
            nu_ano_censo INTEGER NOT NULL,
            qt_mat_bas INTEGER NOT NULL DEFAULT 0,
            qt_mat_inf INTEGER NOT NULL DEFAULT 0,
            qt_mat_fund INTEGER NOT NULL DEFAULT 0,
            qt_mat_med INTEGER NOT NULL DEFAULT 0,
            qt_mat_prof INTEGER NOT NULL DEFAULT 0,
            qt_mat_eja INTEGER NOT NULL DEFAULT 0,
            qt_mat_esp INTEGER NOT NULL DEFAULT 0,
            excluido INTEGER NOT NULL DEFAULT 0
        )
    """)


# IMPORTAÇÃO DOS DADOS

def importar_dados():
    """Lê o CSV em blocos e importa as escolas selecionadas."""

    if not ARQUIVO_CSV.exists():
        raise FileNotFoundError(
            f"Arquivo CSV não encontrado:\n{ARQUIVO_CSV}"
        )

    total_importado = 0
    codigos_vistos = set()

    with psycopg2.connect(dbname = POSTGRES_DB, user = POSTGRES_USER, password = POSTGRES_PASSWORD, host="localhost", port = POSTGRES_PORT) as conexao:
        # Recria a tabela para realizar uma carga inicial limpa.
        criar_tabela(conexao)

        blocos = pd.read_csv(
            ARQUIVO_CSV,
            sep=";",
            encoding="latin1",
            usecols=COLUNAS,
            chunksize=10_000,
            low_memory=False
        )

        for numero_bloco, df in enumerate(blocos, start=1):

            # Filtra as escolas do Nordeste e do Sudeste.
            df = df[df["SG_UF"].isin(UFS_PERMITIDAS)].copy()

            if df.empty:
                continue

            # Garante a ordem correta dos campos.
            df = df[COLUNAS]

            # Verifica códigos repetidos dentro do bloco.
            repetidos_bloco = df["CO_ENTIDADE"].duplicated(keep=False)

            if repetidos_bloco.any():
                print("\nCódigos repetidos dentro do bloco:")
                print(
                    df.loc[
                        repetidos_bloco,
                        ["CO_ENTIDADE", "NO_ENTIDADE", "SG_UF"]
                    ].head(20).to_string(index=False)
                )
                raise ValueError(
                    "Existem códigos CO_ENTIDADE repetidos no bloco."
                )

            # Verifica códigos já encontrados em blocos anteriores.
            repetidos_anteriores = df["CO_ENTIDADE"].isin(codigos_vistos)

            if repetidos_anteriores.any():
                print("\nCódigos repetidos entre blocos:")
                print(
                    df.loc[
                        repetidos_anteriores,
                        ["CO_ENTIDADE", "NO_ENTIDADE", "SG_UF"]
                    ].head(20).to_string(index=False)
                )
                raise ValueError(
                    "Existem códigos CO_ENTIDADE repetidos entre blocos."
                )

            codigos_vistos.update(df["CO_ENTIDADE"].tolist())

            # Renomeia os campos para o padrão do banco.
            df = df.rename(columns=MAPEAMENTO)

            # Substitui valores ausentes por None.
            df = df.astype(object).where(pd.notna(df), None)

            # Converte cada linha em uma tupla para o SQLite.
            registros = [
                tuple(
                    valor.item() if hasattr(valor, "item") else valor
                    for valor in linha
                )
                for linha in df.itertuples(index=False, name=None)
            ]

            try:
                conexao.executemany("""
                    INSERT INTO instituicoesensino (
                        no_entidade,
                        co_entidade,
                        no_uf,
                        sg_uf,
                        co_uf,
                        no_municipio,
                        co_municipio,
                        nu_ano_censo,
                        qt_mat_bas,
                        qt_mat_inf,
                        qt_mat_fund,
                        qt_mat_med,
                        qt_mat_prof,
                        qt_mat_eja,
                        qt_mat_esp
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, registros)

            except sqlite3.IntegrityError as erro:
                # Mostra detalhes caso o SQLite rejeite um registro.
                print(f"\nErro ao inserir o bloco {numero_bloco}: {erro}")

                duplicados_banco = conexao.execute("""
                    SELECT co_entidade
                    FROM instituicoesensino
                    GROUP BY co_entidade
                    HAVING COUNT(*) > 1
                    LIMIT 10
                """).fetchall()

                print("Duplicatas existentes no banco:", duplicados_banco)
                raise

            total_importado += len(registros)

            print(
                f"Bloco {numero_bloco}: "
                f"{len(registros)} instituições inseridas. "
                f"Total: {total_importado}"
            )

        conexao.commit()

    print("\nImportação concluída!")
    print(f"Banco criado em: {ARQUIVO_BANCO}")
    print(f"Total de instituições importadas: {total_importado}")



if __name__ == "__main__":
    importar_dados()
