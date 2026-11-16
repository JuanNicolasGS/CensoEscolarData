from pathlib import Path
import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


variaveis_obrigatorias = [
    "DB_HOST",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD"
]

faltando = [
    variavel
    for variavel in variaveis_obrigatorias
    if not os.getenv(variavel)
]

if faltando:
    raise ValueError(
        f"Variáveis de ambiente não configuradas: {faltando}"
    )


DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "database": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": int(os.getenv("DB_PORT", "5432"))
}


PASTA_DADOS = Path(
    "/home/juniorgomes/Downloads/"
    "microdados_censo_escolar_2025_/"
    "microdados_censo_escolar_2025_v2/dados"
)

ARQUIVO_CSV = PASTA_DADOS / "Tabela_Matricula_2025_V2.csv"



ESTADOS = [
    "MA", "PI", "CE", "RN", "PB",
    "PE", "AL", "SE", "BA",
    "MG", "ES", "RJ", "SP"
]



COLUNAS_CSV = [
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
    "QT_MAT_ESP"
]



MAPEAMENTO_COLUNAS = {
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
    "QT_MAT_ESP": "qt_mat_esp"
}


# 6. CRIAÇÃO DA TABELA

def criar_tabela(cursor):

    cursor.execute("""
        DROP TABLE IF EXISTS instituicoesensino;

        CREATE TABLE instituicoesensino (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

            no_entidade VARCHAR(255) NOT NULL,
            co_entidade INTEGER UNIQUE NOT NULL,

            no_uf VARCHAR(100) NOT NULL,
            sg_uf VARCHAR(2) NOT NULL,
            co_uf INTEGER NOT NULL,

            no_municipio VARCHAR(150) NOT NULL,
            co_municipio INTEGER NOT NULL,

            nu_ano_censo INTEGER NOT NULL,

            qt_mat_bas INTEGER DEFAULT 0,
            qt_mat_inf INTEGER DEFAULT 0,
            qt_mat_fund INTEGER DEFAULT 0,
            qt_mat_med INTEGER DEFAULT 0,
            qt_mat_prof INTEGER DEFAULT 0,
            qt_mat_eja INTEGER DEFAULT 0,
            qt_mat_esp INTEGER DEFAULT 0,

            excluido INTEGER DEFAULT 0
        );
    """)

    print("Tabela criada com sucesso!")


# 7. IMPORTAÇÃO DOS DADOS

def importar_dados():

    conexao = None
    cursor = None

    try:

        conexao = psycopg2.connect(**DB_CONFIG)

        cursor = conexao.cursor()

        print("Conexão com PostgreSQL estabelecida!")

        criar_tabela(cursor)

        conexao.commit()

        codigos_vistos = set()

        total_inseridos = 0

        sql = """
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
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            );
        """

        blocos = pd.read_csv(
            ARQUIVO_CSV,
            usecols=COLUNAS_CSV,
            chunksize=10_000,
            encoding="latin1",
            sep=";"
        )

        for numero_bloco, bloco in enumerate(blocos, start=1):

            bloco = bloco[
                bloco["SG_UF"].isin(ESTADOS)
            ].copy()

            duplicados = bloco["CO_ENTIDADE"].duplicated(
                keep=False
            )

            bloco = bloco[~duplicados].copy()

            bloco = bloco[
                ~bloco["CO_ENTIDADE"].isin(codigos_vistos)
            ].copy()

            codigos_vistos.update(
                bloco["CO_ENTIDADE"].tolist()
            )

            bloco.rename(
                columns=MAPEAMENTO_COLUNAS,
                inplace=True
            )

            bloco = bloco[list(MAPEAMENTO_COLUNAS.values())]


            bloco = bloco.astype(object).where(
                pd.notna(bloco),
                None
            )
            

            dados = list(
                bloco.itertuples(
                    index=False,
                    name=None
                )
            )

            if dados:

                cursor.executemany(sql, dados)

                conexao.commit()

                total_inseridos += len(dados)

            print(
                f"Bloco {numero_bloco} processado. "
                f"Total inserido: {total_inseridos}"
            )

        print("\nImportação concluída!")
        print(f"Total de registros inseridos: {total_inseridos}")

    except Exception as erro:

        if conexao:
            conexao.rollback()

        print(f"Erro durante a importação: {erro}")

        raise

    finally:
        if cursor:
            cursor.close()

        if conexao:
            conexao.close()

        print("Conexão encerrada.")



if __name__ == "__main__":
    importar_dados()